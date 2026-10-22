#!/usr/bin/env bash
# Installs the renderer's dependencies and the open-source Kokoro voice model.
set -e
cd "$(dirname "$0")"
pip install --break-system-packages -q kokoro-onnx soundfile cairosvg pillow numpy "rembg[cpu]"
mkdir -p models
for f in kokoro-v1.0.onnx voices-v1.0.bin; do
  [ -s "models/$f" ] || curl -sSL -o "models/$f" "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/$f"
done
command -v ffmpeg >/dev/null || { echo "ffmpeg missing"; exit 1; }
echo "renderer ready"
