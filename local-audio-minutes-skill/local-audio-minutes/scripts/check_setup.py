#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys


def check_command(name: str) -> bool:
    path = shutil.which(name)
    if path:
        print(f"OK   {name}: {path}")
        return True
    print(f"MISS {name}")
    return False


def check_python_module(name: str) -> bool:
    proc = subprocess.run([sys.executable, "-c", f"import {name}"], text=True, capture_output=True)
    if proc.returncode == 0:
        print(f"OK   python module: {name}")
        return True
    print(f"MISS python module: {name}")
    return False


def main() -> int:
    ok = True
    ok = check_command("ffmpeg") and ok
    ok = check_command("ffprobe") and ok
    ok = check_command("ollama") and ok
    ok = check_command("mlx_audio.stt.generate") and ok
    ok = check_python_module("json") and ok
    print()
    if not ok:
        print("Install missing dependencies, for example:")
        print("  brew install ffmpeg python3 ollama")
        print("  pip3 install mlx-audio")
        print("  ollama pull qwen2.5:7b-instruct")
        return 1
    print("Setup looks ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
