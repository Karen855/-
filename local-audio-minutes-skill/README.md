# Local Audio Minutes Skill

A Codex skill for local-first audio transcription and minutes.

It turns a local `.mp3`, `.m4a`, or `.wav` file into:

- timestamped SRT subtitles
- a cleaned transcript
- Markdown minutes
- an optional clickable local HTML player

The audio stays on your machine. The default ASR path uses Apple Silicon MLX and Qwen ASR; the default summarizer uses Ollama.

## Requirements

- macOS 14+ recommended
- Apple Silicon recommended for MLX ASR
- Python 3.10+
- `ffmpeg`
- `mlx-audio`
- Ollama

## Install

Install command-line dependencies:

```bash
brew install ffmpeg python3 ollama
pip3 install mlx-audio
```

Download at least one Ollama text model. Examples:

```bash
ollama pull qwen2.5:7b-instruct
```

For stronger summarization, use any larger local model you have:

```bash
ollama pull qwen2.5:14b
```

Install the skill:

```bash
./install.sh
```

Restart Codex so it can discover the skill.

## Quick Start

Ask Codex:

```text
Use local-audio-minutes to transcribe /path/to/recording.m4a and create minutes.
```

Or run the script directly:

```bash
python3 ~/.codex/skills/local-audio-minutes/scripts/local_audio_minutes.py \
  "/path/to/recording.m4a" \
  --root "/path/to/AudioMinutes"
```

By default, the original audio is copied into `Audio/`. Add `--move-audio` if you want to move it instead.

Outputs are written as:

```text
AudioMinutes/
├── Audio/
│   └── recording.m4a
└── Project/
    └── YYYYMMDD_recording/
        ├── recording_minutes.md
        ├── recording_player.html
        └── process/
            ├── recording_raw.txt
            ├── recording.srt
            ├── recording_clean.txt
            └── recording_transcript.md
```

## Model Options

Defaults:

```bash
--asr-model mlx-community/Qwen3-ASR-1.7B-8bit
--summary-model qwen2.5:7b-instruct
```

Use another Ollama model:

```bash
python3 ~/.codex/skills/local-audio-minutes/scripts/local_audio_minutes.py \
  "/path/to/recording.m4a" \
  --summary-model llama3.1:8b
```

If your recording is long, enable chunked ASR:

```bash
python3 ~/.codex/skills/local-audio-minutes/scripts/local_audio_minutes.py \
  "/path/to/long-recording.m4a" \
  --chunked
```

If your Ollama model has a different name, pass it explicitly:

```bash
python3 ~/.codex/skills/local-audio-minutes/scripts/local_audio_minutes.py \
  "/path/to/recording.m4a" \
  --summary-model "qwen2.5:14b"
```

## Privacy

This workflow is designed for local processing. It does not upload audio by itself. If you change the scripts or use a cloud model, review your privacy settings.

## Troubleshooting

Check dependencies:

```bash
python3 ~/.codex/skills/local-audio-minutes/scripts/check_setup.py
```

If ASR creates `file.srt.srt`, use output paths without the `.srt` suffix.

If Ollama output contains terminal control characters, the script strips ANSI sequences before writing Markdown.
