#!/bin/sh
set -eu
cd "$(dirname "$0")"
case "$(uname -s)" in
  Darwin|Linux) printf 'Platform %s %s\n' "$(uname -s)" "$(uname -m)" ;;
  *) echo "Use macOS or Linux." >&2; exit 1 ;;
esac
if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  echo "FFmpeg and FFprobe are required. On macOS, install Homebrew from https://brew.sh if needed, then run brew install ffmpeg." >&2
  exit 1
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else "Python 3.11+ is required.")'
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -c 'import cv2, numpy, scipy, PIL, yaml'
echo 'Activate with: source .venv/bin/activate'
