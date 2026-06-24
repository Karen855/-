#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import filecmp
import os
import re
import shutil
import subprocess
from pathlib import Path


DEFAULT_ASR_MODEL = "mlx-community/Qwen3-ASR-1.7B-8bit"
DEFAULT_SUMMARY_MODEL = "qwen2.5:7b-instruct"
NOISE_CHARS = set("嗯呃啊哦唔哼。,.，、！？!?…")
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SPINNER_RE = re.compile(r"[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]")
THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def run(cmd: list[str], *, input_text: str | None = None, timeout: int | None = None) -> str:
    proc = subprocess.run(
        cmd,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stdout}")
    return proc.stdout


def clean_model_output(text: str) -> str:
    text = ANSI_RE.sub("", text)
    text = THINK_RE.sub("", text)
    text = SPINNER_RE.sub("", text)
    text = "".join(ch for ch in text if ord(ch) >= 32 or ch in "\n\r\t")
    text = text.replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def resolve_generated(base: Path, fmt: str) -> Path:
    candidates = [base.with_suffix(f".{fmt}"), Path(str(base) + f".{fmt}")]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def generate_asr(audio: Path, out_base: Path, fmt: str, model: str, language: str) -> Path:
    run(
        [
            "mlx_audio.stt.generate",
            "--model",
            model,
            "--audio",
            str(audio),
            "--output-path",
            str(out_base),
            "--format",
            fmt,
            "--language",
            language,
        ]
    )
    return resolve_generated(out_base, fmt)


def is_noise_text(text: str) -> bool:
    compact = re.sub(r"[\s\W_]+", "", text)
    if not compact:
        return True
    if len(compact) <= 3 and all(ch in NOISE_CHARS for ch in compact):
        return True
    if len(compact) >= 8 and len(set(compact)) <= 2:
        return True
    if all(ch in NOISE_CHARS for ch in compact):
        return True
    return False


def collapse_repeated_units(text: str) -> str:
    result: list[str] = []
    i = 0
    while i < len(text):
        collapsed = False
        for size in range(1, 9):
            unit = text[i : i + size]
            if len(unit) < size or unit.isspace():
                continue
            count = 1
            while text[i + count * size : i + (count + 1) * size] == unit:
                count += 1
            if count >= 4:
                result.append(unit)
                i += count * size
                collapsed = True
                break
        if not collapsed:
            result.append(text[i])
            i += 1
    return re.sub(r"\s+", " ", "".join(result)).strip()


def clean_transcript_text(text: str) -> str:
    text = re.sub(r"([嗯哦啊呃])\1{2,}", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    lines = []
    for line in text.splitlines():
        line = collapse_repeated_units(line.strip())
        if line and not is_noise_text(line):
            lines.append(line)
    return "\n".join(lines).strip() + "\n"


def parse_srt_time(value: str) -> float:
    match = re.match(r"(\d+):(\d+):(\d+),(\d+)", value.strip())
    if not match:
        return 0.0
    h, m, s, ms = map(int, match.groups())
    return h * 3600 + m * 60 + s + ms / 1000


def display_time(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def srt_items(srt: Path) -> list[dict]:
    items = []
    for block in re.split(r"\n\s*\n", srt.read_text(encoding="utf-8", errors="ignore").strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        begin, end = [part.strip() for part in lines[1].split("-->", 1)]
        text = collapse_repeated_units(" ".join(lines[2:]))
        if is_noise_text(text):
            continue
        items.append({"start": parse_srt_time(begin), "end": parse_srt_time(end), "text": text})
    return items


def write_transcript_md(path: Path, stem: str, items: list[dict]) -> None:
    lines = [f"# Transcript: {stem}", ""]
    for item in items:
        lines.append(display_time(item["start"]))
        lines.append(item["text"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def chapter_hints(items: list[dict], max_items: int = 80) -> str:
    if not items:
        return "No timestamped transcript items."
    scored = []
    keywords = [
        "decision",
        "action",
        "todo",
        "risk",
        "customer",
        "client",
        "project",
        "AI",
        "model",
        "sales",
        "marketing",
        "plan",
        "idea",
        "反思",
        "客户",
        "项目",
        "行动",
        "风险",
        "计划",
        "想法",
    ]
    for item in items:
        score = min(len(item["text"]) // 45, 4)
        score += sum(3 for keyword in keywords if keyword.lower() in item["text"].lower())
        if score > 0 or len(item["text"]) > 90:
            scored.append((score, item["start"], item["text"]))
    sample_gap = max(1, len(items) // 24)
    sampled = [(1, item["start"], item["text"]) for item in items[::sample_gap]]
    selected = sampled + sorted(scored, key=lambda row: (-row[0], row[1]))[:max_items]
    dedup = []
    seen = set()
    for score, start, text in sorted(selected, key=lambda row: row[1]):
        bucket = int(start // 120)
        if bucket in seen:
            continue
        seen.add(bucket)
        dedup.append((score, start, text))
        if len(dedup) >= max_items:
            break
    return "\n".join(f"[{display_time(start)}] {text[:180]}" for _score, start, text in dedup)


def make_minutes(
    stem: str,
    audio: Path,
    raw_txt: Path,
    clean_txt: Path,
    srt: Path,
    transcript_md: Path,
    summary_model: str,
) -> str:
    items = srt_items(srt)
    coverage = display_time(max((item["end"] for item in items), default=0))
    clean_text = clean_txt.read_text(encoding="utf-8", errors="ignore")
    sample = "\n".join(f"[{display_time(i['start'])}] {i['text']}" for i in items[:: max(1, len(items) // 240)][:240])
    prompt = f"""You are creating local audio minutes from an automatic transcript.

Rules:
- Do not ask follow-up questions.
- Do not invent facts, timestamps, URLs, or speakers.
- If the recording is mixed or noisy, say so clearly.
- Use the transcript timestamps as anchors.
- Output Markdown only.

Required structure:

# Audio Minutes: {stem}

> Coverage: {coverage}
> Source: local ASR

## One-line Summary
## Key Moments
## Detailed Notes
## Action Items
## Searchable Timeline
## Transcript Coverage
## Local Links

For long mixed recordings, use this structure instead:

# Archive Minutes: {stem}
## One-line Judgment
## Tier 1: High-value Moments
## Tier 2: Useful Context
## Tier 3: Background Anchors
## Action Items
## Transcript Coverage
## Local Links

Local links to include:
- Audio: {audio}
- Raw transcript: {raw_txt}
- Clean transcript: {clean_txt}
- Timestamped transcript: {srt}
- Transcript document: {transcript_md}

Timestamp hints:
{chapter_hints(items)}

Transcript sample:
{sample}

Clean transcript:
{clean_text[:60000]}

Final instruction: write the Markdown minutes now. Do not include fake web links.
"""
    output = clean_model_output(run(["ollama", "run", "--nowordwrap", summary_model], input_text=prompt, timeout=900))
    local_links = "\n".join(
        [
            "## Local Links",
            f"- Audio: [{audio.name}](<{audio}>)",
            f"- Raw transcript: [{raw_txt.name}](<{raw_txt}>)",
            f"- Clean transcript: [{clean_txt.name}](<{clean_txt}>)",
            f"- SRT: [{srt.name}](<{srt}>)",
            f"- Transcript document: [{transcript_md.name}](<{transcript_md}>)",
            "",
        ]
    )
    if "## Local Links" in output:
        output = output.split("## Local Links", 1)[0].rstrip() + "\n\n" + local_links
    else:
        output = output.rstrip() + "\n\n" + local_links
    return output


def default_root_for(audio: Path) -> Path:
    return audio.parent


def store_audio(audio: Path, audio_dir: Path, *, move: bool) -> Path:
    audio_dir.mkdir(parents=True, exist_ok=True)
    target = audio_dir / audio.name
    if audio == target:
        return audio
    if target.exists():
        if target.stat().st_size == audio.stat().st_size and filecmp.cmp(audio, target, shallow=False):
            if move:
                audio.unlink()
            return target
        raise SystemExit(f"Target audio exists with different content: {target}")
    if move:
        shutil.move(str(audio), str(target))
    else:
        shutil.copy2(audio, target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--language", default="zh")
    parser.add_argument("--asr-model", default=os.environ.get("LOCAL_AUDIO_ASR_MODEL", DEFAULT_ASR_MODEL))
    parser.add_argument("--summary-model", default=os.environ.get("LOCAL_AUDIO_SUMMARY_MODEL", DEFAULT_SUMMARY_MODEL))
    parser.add_argument("--chunked", action="store_true")
    parser.add_argument("--move-audio", action="store_true", help="Move audio into Audio/ instead of copying it")
    parser.add_argument("--no-summary", action="store_true")
    args = parser.parse_args()

    audio = args.audio.expanduser().resolve()
    if not audio.exists():
        raise SystemExit(f"Audio not found: {audio}")

    root = (args.root.expanduser().resolve() if args.root else default_root_for(audio))
    stem = audio.stem
    date_match = re.match(r"(20\d{6})", stem)
    date = date_match.group(1) if date_match else dt.datetime.now().strftime("%Y%m%d")
    project = root / "Project" / f"{date}_{stem}"
    process = project / "process"
    process.mkdir(parents=True, exist_ok=True)

    stored_audio = store_audio(audio, root / "Audio", move=args.move_audio)

    raw_base = process / f"{stem}_raw"
    srt_path = process / f"{stem}.srt"
    raw_txt = process / f"{stem}_raw.txt"
    clean_txt = process / f"{stem}_clean.txt"
    transcript_md = process / f"{stem}_transcript.md"
    minutes = project / f"{stem}_minutes.md"
    player = project / f"{stem}_player.html"

    if args.chunked:
        script = Path(__file__).with_name("chunked_asr.py")
        run(
            [
                "python3",
                str(script),
                str(stored_audio),
                "--out",
                str(srt_path),
                "--model",
                args.asr_model,
                "--language",
                args.language,
            ]
        )
        raw_txt.write_text("\n".join(item["text"] for item in srt_items(srt_path)) + "\n", encoding="utf-8")
    else:
        raw_txt = generate_asr(stored_audio, raw_base, "txt", args.asr_model, args.language)
        generated_srt = generate_asr(stored_audio, process / stem, "srt", args.asr_model, args.language)
        if generated_srt != srt_path:
            shutil.copy2(generated_srt, srt_path)

    clean_txt.write_text(clean_transcript_text(raw_txt.read_text(encoding="utf-8", errors="ignore")), encoding="utf-8")
    items = srt_items(srt_path)
    write_transcript_md(transcript_md, stem, items)

    if not args.no_summary:
        minutes.write_text(
            make_minutes(stem, stored_audio, raw_txt, clean_txt, srt_path, transcript_md, args.summary_model),
            encoding="utf-8",
        )

    run(
        [
            "python3",
            str(Path(__file__).with_name("build_audio_player.py")),
            "--audio",
            str(stored_audio),
            "--srt",
            str(srt_path),
            "--minutes",
            str(minutes),
            "--out",
            str(player),
        ]
    )

    print(f"Project: {project}")
    print(f"Minutes: {minutes}")
    print(f"Player: {player}")
    print(f"SRT: {srt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
