# plaud-converter

Batch convert video/audio files to MP3 for import into [Plaud](https://www.plaud.ai/), with optional merging into chunks.

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

# Convert and automatically merge into chunks
python3 convert.py /path/to/lectures --merge

# Custom output directory + merge with prefix
python3 convert.py /path/to/lectures -o ~/output --merge --merge-prefix "course"

# Non-interactive (skip merge prompt)
python3 convert.py /path/to/lectures -y
```

## Flags

| Flag | Description |
|---|---|
| `-o`, `--output` | Output directory (default: `<input_dir>/converted/`) |
| `--max-size` | Max file size in MB (default: 490) |
| `--merge` | Merge converted files into chunks fitting Plaud limits |
| `--merge-prefix` | Prefix for merged filenames (default: `merged`) |
| `-y`, `--yes` | Skip interactive prompts |

## How it works

1. Recursively scans the input directory for supported media files
2. Skips files longer than 5 hours
3. Calculates the optimal bitrate to keep each file under the size limit
4. Converts to MP3 (audio only) via ffmpeg at up to 128 kbps
5. Prefixes output filenames with subfolder names to prevent collisions

### Merge mode

When `--merge` is passed (or confirmed interactively after conversion):

- Groups converted files sequentially into chunks
- Each chunk fits within **5 hours** and **490 MB**
- Saves to `<output>/merged/` as `<prefix>_part1.mp3`, `<prefix>_part2.mp3`, ...
- Uses lossless concat when possible, falls back to re-encoding if needed

## Claude Code skill

The `.claude/skills/plaud-convert.md` file lets Claude Code use this tool automatically when you mention Plaud or need to convert media for transcription.
