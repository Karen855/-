#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import re
from pathlib import Path
from urllib.parse import quote


def parse_srt_time(value: str) -> float:
    match = re.match(r"(\d+):(\d+):(\d+),(\d+)", value.strip())
    if not match:
        return 0.0
    h, m, s, ms = map(int, match.groups())
    return h * 3600 + m * 60 + s + ms / 1000


def display_time(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def parse_srt(path: Path) -> list[dict]:
    items: list[dict] = []
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8", errors="ignore").strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        begin, end = [part.strip() for part in lines[1].split("-->", 1)]
        items.append(
            {
                "start": parse_srt_time(begin),
                "end": parse_srt_time(end),
                "text": " ".join(lines[2:]),
            }
        )
    return items


def relative_href(target: Path, base_dir: Path) -> str:
    return quote(Path(os.path.relpath(target, base_dir)).as_posix(), safe="/._-+")


def make_chapters(items: list[dict], max_items: int = 18) -> list[dict]:
    if not items:
        return []
    step = max(1, len(items) // max_items)
    chapters = []
    for item in items[::step][:max_items]:
        text = item["text"].strip()
        title = re.split(r"[。！？.!?]", text, maxsplit=1)[0][:36] or "Audio segment"
        chapters.append({"start": item["start"], "title": title, "summary": text[:140]})
    return chapters


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--srt", type=Path, required=True)
    parser.add_argument("--minutes", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    audio = args.audio.expanduser().resolve()
    srt = args.srt.expanduser().resolve()
    minutes = args.minutes.expanduser().resolve() if args.minutes else None
    out = args.out.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    items = parse_srt(srt)
    data = {
        "audio": relative_href(audio, out.parent),
        "items": items,
        "chapters": make_chapters(items),
    }
    links = []
    if minutes and minutes.exists():
        links.append(f'<a href="{html.escape(relative_href(minutes, out.parent))}">Minutes</a>')
    links.append(f'<a href="{html.escape(relative_href(srt, out.parent))}">SRT</a>')

    out.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Local Audio Minutes: {html.escape(audio.stem)}</title>
  <style>
    body {{ margin: 0; background: #f7f7f4; color: #222; font: 15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    header {{ position: sticky; top: 0; z-index: 2; background: rgba(247,247,244,.96); border-bottom: 1px solid #ddd; padding: 14px 20px; }}
    h1 {{ margin: 0 0 10px; font-size: 20px; }}
    audio {{ width: 100%; }}
    main {{ display: grid; grid-template-columns: 340px 1fr; gap: 16px; max-width: 1280px; margin: 0 auto; padding: 18px 20px 40px; }}
    aside, section {{ background: white; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }}
    aside {{ align-self: start; position: sticky; top: 112px; max-height: calc(100vh - 130px); overflow: auto; }}
    .head {{ padding: 12px 14px; border-bottom: 1px solid #ddd; font-weight: 700; }}
    .chapter, .row {{ display: grid; grid-template-columns: 82px 1fr; gap: 12px; padding: 10px 14px; border-bottom: 1px solid #eee; cursor: pointer; }}
    .chapter:hover, .row:hover {{ background: #fafaf7; }}
    .row.active {{ background: #fff7d6; box-shadow: inset 4px 0 0 #0f766e; }}
    .time {{ color: #0f766e; font-variant-numeric: tabular-nums; font-weight: 650; }}
    .summary {{ color: #667085; font-size: 13px; }}
    .tools {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; color: #667085; font-size: 13px; }}
    input {{ min-width: 240px; flex: 1; padding: 8px 10px; border: 1px solid #ddd; border-radius: 6px; }}
    a {{ color: #0f766e; text-decoration: none; }}
    @media (max-width: 820px) {{ main {{ grid-template-columns: 1fr; padding: 12px; }} aside {{ position: static; max-height: none; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Local Audio Minutes: {html.escape(audio.stem)}</h1>
    <audio id="player" controls preload="metadata" src="{html.escape(data["audio"])}"></audio>
    <div class="tools">
      <input id="search" type="search" placeholder="Search transcript" />
      <span>{len(items)} transcript rows · coverage to {display_time(items[-1]["end"]) if items else "00:00:00"}</span>
      <span>{" · ".join(links)}</span>
    </div>
  </header>
  <main>
    <aside><div class="head">Chapters</div><div id="chapters"></div></aside>
    <section><div class="head">Transcript</div><div id="transcript"></div></section>
  </main>
  <script>
    const data = {json.dumps(data, ensure_ascii=False)};
    const player = document.getElementById('player');
    const chapters = document.getElementById('chapters');
    const transcript = document.getElementById('transcript');
    const search = document.getElementById('search');
    const fmt = s => `${{String(Math.floor(s/3600)).padStart(2,'0')}}:${{String(Math.floor((s%3600)/60)).padStart(2,'0')}}:${{String(Math.floor(s%60)).padStart(2,'0')}}`;
    const esc = s => String(s).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
    function seek(s) {{ player.currentTime = s; player.play(); }}
    function renderChapters() {{
      chapters.innerHTML = data.chapters.map(ch => `<div class="chapter" data-start="${{ch.start}}"><div class="time">${{fmt(ch.start)}}</div><div><b>${{esc(ch.title)}}</b><div class="summary">${{esc(ch.summary)}}</div></div></div>`).join('');
      chapters.querySelectorAll('.chapter').forEach(el => el.onclick = () => seek(Number(el.dataset.start)));
    }}
    function renderRows(rows) {{
      transcript.innerHTML = rows.map((it, i) => `<div class="row" data-index="${{i}}" data-start="${{it.start}}"><div class="time">${{fmt(it.start)}}</div><div>${{esc(it.text)}}</div></div>`).join('');
      transcript.querySelectorAll('.row').forEach(el => el.onclick = () => seek(Number(el.dataset.start)));
    }}
    search.oninput = () => {{
      const q = search.value.trim().toLowerCase();
      renderRows(q ? data.items.filter(it => it.text.toLowerCase().includes(q)) : data.items);
    }};
    player.ontimeupdate = () => {{
      const t = player.currentTime;
      const rows = [...transcript.querySelectorAll('.row')];
      let active = null;
      for (const row of rows) if (Number(row.dataset.start) <= t) active = row;
      rows.forEach(row => row.classList.toggle('active', row === active));
    }};
    renderChapters();
    renderRows(data.items);
  </script>
</body>
</html>
""",
        encoding="utf-8",
    )
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

