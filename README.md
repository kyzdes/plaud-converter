# plaud-converter

Batch convert video/audio files to MP3 for import into [Plaud](https://www.plaud.ai/), with per-folder merging and HTML reporting.

## Plaud import limits

| Constraint | Limit |
|---|---|
| Formats | MP3, MP4, WAV, OGG, RMVB, RM, DIVX, TS, M2TS, 3GP, F4V, ASR |
| Max duration | 5 hours |
| Max file size | 500 MB |

## Requirements

- Python 3.9+
- ffmpeg

```bash
brew install ffmpeg  # macOS
```

## Usage

```bash
# Convert only
python3 convert.py /path/to/lectures

# Convert + merge by folder + HTML report (opens in browser)
python3 convert.py /path/to/lectures --merge --report

# Non-interactive, custom output
python3 convert.py /path/to/lectures -o ~/output --merge --report -y

# Don't auto-open report
python3 convert.py /path/to/lectures --merge --report --no-open
```

## Flags

| Flag | Description |
|---|---|
| `-o`, `--output` | Output directory (default: `<input_dir>/converted/`) |
| `--max-size` | Max file size in MB (default: 490) |
| `--merge` | Merge converted files by folder (1 folder = 1 topic) |
| `--report` | Generate HTML report with statistics |
| `--no-open` | Don't auto-open report in browser |
| `-y`, `--yes` | Skip interactive prompts |

## How it works

### Convert

1. Recursively scans the input directory for supported media files
2. Skips files longer than 5 hours and macOS resource fork files
3. Calculates the optimal bitrate to keep each file under the size limit
4. Converts to MP3 (audio only) via ffmpeg at up to 128 kbps
5. Prefixes output filenames with subfolder names to prevent collisions

### Merge

Groups converted files by source folder — **1 folder = 1 topic = 1 merged file**:

- Files within each folder are concatenated in natural sort order (1, 2, 3, ..., 10, 11)
- If a folder exceeds 5 hours or 490 MB, it splits into numbered parts
- Merged files are saved to `<output>/merged/`

### Report

Generates an HTML report with:

- Summary cards (source/converted/merged counts, sizes, compression ratio, timing)
- Folder-to-merged mapping validation (1:1 match check)
- Per-topic merged file cards with duration and size progress bars vs Plaud limits
- Source folder breakdown table
- Full file listings for source and converted files

## Claude Code skill

The `.claude/skills/plaud-convert.md` file lets Claude Code use this tool automatically when you mention Plaud or need to convert media for transcription.
