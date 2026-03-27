---
name: plaud-convert
description: Convert video/audio files to MP3 for Plaud import, with per-folder merging and HTML reporting. Use when user mentions Plaud, wants to convert lectures/recordings for transcription, or needs to batch-convert and merge media files with size/duration limits. Merge groups files by source folder so each merged file = 1 topic/lecture. Report shows full statistics with source/converted/merged breakdowns.
---

# Plaud Converter

Convert media files to MP3 for import into Plaud, with per-folder merge and HTML report.

## Plaud import constraints

- **Supported formats**: MP3, MP4, WAV, OGG, RMVB, RM, DIVX, TS, M2TS, 3GP, F4V, ASR
- **Max file length**: 5 hours
- **Max file size**: 500 MB (target 490 MB for safety margin)

## How to use

```bash
python3 convert.py <input_directory> [-o <output_dir>] [--merge] [--report] [--no-open] [-y]
```

### Convert, merge by folder, and generate report

```bash
python3 convert.py /path/to/lectures --merge --report
```

### Flags

| Flag | Description |
|---|---|
| `--merge` | Merge converted files by folder (1 folder = 1 topic) |
| `--report` | Generate HTML report with full statistics |
| `--no-open` | Don't auto-open the report in browser |
| `-y` | Skip interactive prompts |
| `-o` | Custom output directory |
| `--max-size` | Max file size in MB (default: 490) |

### Merge logic

- **1 source folder = 1 merged file** (= 1 topic / 1 lecture)
- Files within each folder are merged in natural sort order (1, 2, 3, ..., 10)
- If a folder exceeds 5h or 490MB, splits into `folder_part1.mp3`, `folder_part2.mp3`
- Output goes to `<output>/merged/`

### HTML Report

The report includes:
- Summary cards: source/converted/merged counts, sizes, compression ratio
- Folders vs merged match check (1:1 mapping validation)
- Per-topic merged file cards with duration/size progress bars
- Source folder breakdown table
- Full source and converted file listings

### Interactive mode (default)

Without `--merge`/`--report`/`-y`, the script prompts after each step:
1. After conversion: "Merge files by folder?"
2. After merge: "Generate HTML report?"

### Requirements

- Python 3.9+
- ffmpeg (`brew install ffmpeg`)
