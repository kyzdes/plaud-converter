---
name: plaud-convert
description: Convert video/audio files to MP3 for Plaud import, with optional per-folder merging. Use when user mentions Plaud, wants to convert lectures/recordings for transcription, or needs to batch-convert and merge media files with size/duration limits. Merge groups files by source folder so each merged file = 1 topic/lecture.
---

# Plaud Converter

Convert media files to MP3 for import into Plaud, with per-folder merge.

## Plaud import constraints

- **Supported formats**: MP3, MP4, WAV, OGG, RMVB, RM, DIVX, TS, M2TS, 3GP, F4V, ASR
- **Max file length**: 5 hours
- **Max file size**: 500 MB (target 490 MB for safety margin)

## How to convert

```bash
python3 convert.py <input_directory> [-o <output_directory>] [--max-size <MB>] [--merge] [-y]
```

### Convert only

```bash
python3 convert.py /path/to/lectures
```

### Convert and merge by folder

```bash
python3 convert.py /path/to/lectures --merge
```

### Merge logic

- **1 source folder = 1 merged file** (= 1 topic / 1 lecture)
- Files within each folder are merged in natural sort order (1, 2, 3, ..., 10)
- If a folder's total exceeds 5h or 490MB, it splits into `folder_part1.mp3`, `folder_part2.mp3`
- Merged files are named after the source folder
- Output goes to `<output>/merged/`

### Interactive mode (default)

If `--merge` is not passed and `-y` is not set, the script asks after conversion whether to merge.

### Requirements

- Python 3.9+
- ffmpeg (`brew install ffmpeg`)
