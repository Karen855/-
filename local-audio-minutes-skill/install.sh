#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="$REPO_DIR/local-audio-minutes"
SKILL_DST="${CODEX_HOME:-$HOME/.codex}/skills/local-audio-minutes"

mkdir -p "$(dirname "$SKILL_DST")"
rm -rf "$SKILL_DST"
cp -R "$SKILL_SRC" "$SKILL_DST"

echo "Installed skill:"
echo "  $SKILL_DST"
echo
echo "Next, check local dependencies:"
echo "  python3 \"$SKILL_DST/scripts/check_setup.py\""
echo
echo "Common setup commands:"
echo "  brew install ffmpeg python3 ollama"
echo "  pip3 install mlx-audio"
echo "  ollama pull qwen2.5:7b-instruct"
echo
echo "Restart Codex after installing the skill."

