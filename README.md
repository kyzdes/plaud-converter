# plaud-converter

Batch convert video/audio files to MP3 for import into [Plaud](https://www.plaud.ai/).

## Plaud import limits

| Constraint | Limit |
|---|---|
| Formats | MP3, MP4, WAV, OGG, RMVB, RM, DIVX, TS, M2TS, 3GP, F4V, ASR |
| Max duration | 5 hours |
| Max file size | 500 MB |

## Requirements

- Python 3.10+
- ffmpeg

```bash
brew install ffmpeg  # macOS
```

## Usage

```bash
# Convert all media files in a folder
python3 convert.py /path/to/lectures

# Custom output directory
python3 convert.py /path/to/lectures -o ~/Desktop/output

# Custom max file size (default: 490 MB)
python3 convert.py /path/to/lectures --max-size 400
```

Output goes to `<input_dir>/converted/` by default.

## How it works

1. Recursively scans the input directory for supported media files
2. Skips files longer than 5 hours
3. Calculates the optimal bitrate to keep each file under the size limit
4. Converts to MP3 (audio only) via ffmpeg at up to 128 kbps
5. Prefixes output filenames with subfolder names to prevent collisions

## Claude Code skill

The `.claude/skills/plaud-convert.md` file lets Claude Code use this tool automatically when you mention Plaud or need to convert media for transcription.
