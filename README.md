# Face Timelapse for macOS

Build a stabilized seven-second face timelapse from a folder of dated selfies. The pipeline uses Apple Vision for face landmarks and person segmentation, Pillow/NumPy for alignment and grading, and FFmpeg for H.264 encoding.

Outputs:

- `face_timelapse_square.mp4` — 1080×1080, 30 fps
- `face_timelapse_story.mp4` — 1080×1920, 30 fps
- `face_timelapse_square.gif` — 480×480, looping

Source photos are never modified, moved, or deleted.

## Requirements

- macOS 13 or newer on Apple silicon or Intel
- Xcode Command Line Tools
- Python 3.10+
- FFmpeg

Install the command-line tools and dependencies:

```bash
xcode-select --install
brew install python ffmpeg
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Homebrew is only needed when Python or FFmpeg is not already installed.

## Clone and run

```bash
git clone YOUR_REPOSITORY_URL face-timelapse
cd face-timelapse
```

Copy your photos into the repository root. Supported formats are JPG, JPEG, PNG, and HEIC. Filenames such as `Photo on 2-6-25 at 1.28 PM.jpg` are recognized automatically.

```bash
source .venv/bin/activate
./tools/run_all.sh
```

Processing hundreds of photos may take several minutes. Intermediate files are written under `work/` and ignored by Git.

## Excluding private or unwanted photos

```bash
cp exclude.example.txt exclude.txt
```

Edit `exclude.txt` using either exact filenames or complete dates:

```text
Photo on 1-2-24 at 3.04 PM.jpg
date:2024-10-16
```

The exclusion file is ignored by Git so private filenames do not get committed accidentally.

## How selection works

1. Apple Vision detects the largest face and its eyes, nose, and mouth.
2. Side-facing and very small faces are rejected.
3. The best photo per day is scored using alignment, expression, eye openness, sharpness, exposure, resolution, and multi-face penalties.
4. Up to 180 days are distributed across the available years.
5. Faces are similarity-aligned to a common position and scale.
6. Person masks stabilize skin tone and soften background changes.
7. Dates, a progress bar, and a one-second ending hold are added.

## Privacy

All processing is local. The scripts do not upload photos or call a network API. Before sharing a fork, verify that `git status` does not list photos, videos, `work/`, or `exclude.txt`.

```bash
git status --short
git ls-files
```

## Rebuilding

Run the same command again:

```bash
./tools/run_all.sh
```

The pipeline stops on the first failed stage. To start with clean intermediates, move `work/` elsewhere or delete it yourself after confirming it contains no source photos.

## License

MIT
