#!/bin/bash
# Builds a 7-second face timelapse from photos in the repository root.
# Reads JPG/JPEG/PNG/HEIC plus optional exclude.txt; writes work/ and three final files.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
command -v clang >/dev/null || { echo "clang is required (install Xcode Command Line Tools)." >&2; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg is required. See README.md." >&2; exit 1; }
"$PYTHON" -c 'import PIL, numpy' || { echo "Install Python dependencies: python3 -m pip install -r requirements.txt" >&2; exit 1; }

mkdir -p work/mask
"$PYTHON" tools/pipeline.py inventory
clang -fobjc-arc -framework Foundation -framework Vision -framework ImageIO -framework CoreGraphics tools/detect.m -o tools/detect
clang -fobjc-arc -framework Foundation -framework Vision -framework CoreImage -framework CoreGraphics tools/segment.m -o tools/segment
tools/detect . work/detect.json
"$PYTHON" tools/pipeline.py render
tools/segment work/warp work/mask
"$PYTHON" tools/pipeline.py grade
"$PYTHON" tools/pipeline.py compose
ffmpeg -loglevel error -y -framerate 30 -i work/out_square/%04d.jpg -c:v libx264 -profile:v high -pix_fmt yuv420p -colorspace bt709 -color_primaries bt709 -color_trc bt709 -movflags +faststart face_timelapse_square.mp4
ffmpeg -loglevel error -y -framerate 30 -i work/out_story/%04d.jpg -c:v libx264 -profile:v high -pix_fmt yuv420p -colorspace bt709 -color_primaries bt709 -color_trc bt709 -movflags +faststart face_timelapse_story.mp4
echo "Created face_timelapse_square.mp4, face_timelapse_story.mp4, and face_timelapse_square.gif"
