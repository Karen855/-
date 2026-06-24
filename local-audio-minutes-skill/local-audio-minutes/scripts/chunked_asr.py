#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import re
import shutil
import subprocess
from pathlib import Path


DEFAULT_ASR_MODEL = "mlx-community/Qwen3-ASR-1.7B-8bit"
NOISE_CHARS = set("嗯呃啊哦唔哼。,.，、！？!?…")


def run(cmd: list[str], *, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, text=True, capture_output=True, timeout=timeout)


def duration_seconds(audio: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        proc = run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(audio),
            ]
        )
        return float(proc.stdout.strip())
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    proc = subprocess.run([ffmpeg, "-hide_banner", "-i", str(audio)], text=True, capture_output=True)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
    if not match:
        raise RuntimeError("Could not read audio duration")
    h, m, s = match.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def stamp(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 3600:02d}-{(seconds % 3600) // 60:02d}-{seconds % 60:02d}"


def parse_time(value: str) -> int:
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(",")
    return (int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 1000 + int(millis)


def format_time(ms: int) -> str:
    hours = ms // 3_600_000
    ms %= 3_600_000
    minutes = ms // 60_000
    ms %= 60_000
    seconds = ms // 1000
    millis = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def is_noise_text(text: str) -> bool:
    compact = re.sub(r"[\s\W_]+", "", text)
    if not compact:
        return True
    if len(compact) <= 3 and all(ch in NOISE_CHARS for ch in compact):
        return True
    if len(compact) >= 8 and len(set(compact)) <= 2:
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


def shift_srt(text: str, offset_seconds: float, start_index: int) -> tuple[list[str], int]:
    offset = int(round(offset_seconds * 1000))
    blocks_out: list[str] = []
    index = start_index
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [line.rstrip() for line in block.splitlines()]
        if len(lines) < 2 or "-->" not in lines[1]:
            continue
        body = collapse_repeated_units("\n".join(lines[2:]).strip())
        if is_noise_text(body):
            continue
        begin, end = [part.strip() for part in lines[1].split("-->", 1)]
        blocks_out.append(
            f"{index}\n"
            f"{format_time(parse_time(begin) + offset)} --> {format_time(parse_time(end) + offset)}\n"
            f"{body}\n"
        )
        index += 1
    return blocks_out, index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_ASR_MODEL)
    parser.add_argument("--language", default="zh")
    parser.add_argument("--chunk-seconds", type=int, default=600)
    parser.add_argument("--chunk-bitrate", default="64k")
    parser.add_argument("--asr-timeout", type=int, default=300)
    args = parser.parse_args()

    audio = args.audio.expanduser().resolve()
    out = args.out.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    chunk_dir = out.parent / f"{audio.stem}_asr_chunks"
    chunk_dir.mkdir(exist_ok=True)
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"

    total = duration_seconds(audio)
    chunk_count = math.ceil(total / args.chunk_seconds)
    blocks: list[str] = []
    next_index = 1

    for i in range(chunk_count):
        start = i * args.chunk_seconds
        length = min(args.chunk_seconds, total - start)
        base = chunk_dir / f"chunk_{i:03d}_{stamp(start)}"
        chunk = base.with_suffix(".m4a")
        srt = base.with_suffix(".srt")

        if not srt.exists():
            subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    str(start),
                    "-t",
                    str(length),
                    "-i",
                    str(audio),
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-codec:a",
                    "aac",
                    "-b:a",
                    args.chunk_bitrate,
                    "-y",
                    str(chunk),
                ],
                check=True,
            )
            subprocess.run(
                [
                    "mlx_audio.stt.generate",
                    "--model",
                    args.model,
                    "--audio",
                    str(chunk),
                    "--output-path",
                    str(base),
                    "--format",
                    "srt",
                    "--language",
                    args.language,
                ],
                check=True,
                timeout=args.asr_timeout,
            )

        if srt.exists():
            shifted, next_index = shift_srt(srt.read_text(errors="ignore"), start, next_index)
            blocks.extend(shifted)
            print(f"[{i + 1}/{chunk_count}] {stamp(start)} blocks={len(shifted)} total={next_index - 1}")

    out.write_text("\n".join(blocks), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

