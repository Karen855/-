---
name: local-audio-minutes
description: Create local-first audio transcripts, timestamped subtitles, Markdown minutes, and clickable local HTML players from local .mp3, .m4a, or .wav recordings using MLX/Qwen ASR and Ollama or another local text model. Use when the user provides a local audio path and wants private transcription, searchable notes, chapters, SRT, or a local replay player.
---

# Local Audio Minutes

Use this skill for local audio transcription and minutes. Keep audio and transcripts on disk; do not upload recordings unless the user explicitly asks for a cloud workflow.

## Quick Workflow

1. Verify the audio path exists.
2. Check setup if needed:

```bash
python3 ~/.codex/skills/local-audio-minutes/scripts/check_setup.py
```

3. Run the main script:

```bash
python3 ~/.codex/skills/local-audio-minutes/scripts/local_audio_minutes.py "/path/to/audio.m4a"
```

4. For long recordings, use chunked ASR:

```bash
python3 ~/.codex/skills/local-audio-minutes/scripts/local_audio_minutes.py "/path/to/audio.m4a" --chunked
```

## Output Layout

By default, outputs live next to the input recording's parent folder unless `--root` is provided.

```text
<root>/
├── Audio/
│   └── <audio-stem>.<ext>
└── Project/
    └── <YYYYMMDD>_<audio-stem>/
        ├── <audio-stem>_minutes.md
        ├── <audio-stem>_player.html
        └── process/
            ├── <audio-stem>_raw.txt
            ├── <audio-stem>.srt
            ├── <audio-stem>_clean.txt
            └── <audio-stem>_transcript.md
```

Copy the original audio into `Audio/` by default; use `--move-audio` only when the user explicitly wants to move it. Generated files should go under `Project/`.

## Models

Defaults are conservative and easy to replace:

- ASR: `mlx-community/Qwen3-ASR-1.7B-8bit`
- Summary: `qwen2.5:7b-instruct`

The user can override them:

```bash
python3 ~/.codex/skills/local-audio-minutes/scripts/local_audio_minutes.py \
  "/path/to/audio.m4a" \
  --asr-model "mlx-community/Qwen3-ASR-1.7B-8bit" \
  --summary-model "qwen2.5:14b"
```

If a model is unavailable, list local Ollama models with:

```bash
ollama list
```

Then rerun with `--summary-model <model-name>`.

## Minutes Style

The Markdown note should be honest and useful, not artificially grand.

Default sections:

```text
# Audio Minutes: <audio-stem>

## One-line Summary
## Key Moments
## Detailed Notes
## Action Items
## Searchable Timeline
## Transcript Coverage
## Local Links
```

For long mixed recordings, use a tiered archive structure:

```text
# Archive Minutes: <audio-stem>
## One-line Judgment
## Tier 1: High-value Moments
## Tier 2: Useful Context
## Tier 3: Background Anchors
## Action Items
## Transcript Coverage
## Local Links
```

Do not force value. If most of the recording is background, say so and keep it searchable.

## Player

The HTML player should:

- load the local audio by relative path
- show clickable chapters
- show timestamped transcript rows
- click transcript rows to seek
- support simple text search

Build it through the main script or directly:

```bash
python3 ~/.codex/skills/local-audio-minutes/scripts/build_audio_player.py \
  --audio "/path/to/root/Audio/audio.m4a" \
  --srt "/path/to/root/Project/YYYYMMDD_audio/process/audio.srt" \
  --minutes "/path/to/root/Project/YYYYMMDD_audio/audio_minutes.md" \
  --out "/path/to/root/Project/YYYYMMDD_audio/audio_player.html"
```

## Quality Rules

- Prefer timestamped SRT before summarizing.
- Clean repeated ASR noise and filler before summarization.
- Strip ANSI/control characters from local model output before writing files.
- Do not invent timestamps, speakers, facts, URLs, or links.
- Use local file links for generated artifacts.
- For long audio, compare final SRT timestamp with audio duration. If coverage is short, rerun with `--chunked`.
