---
name: plaud-convert
description: Convert video/audio files to MP3 for Plaud import, with optional merging into chunks. Use when user mentions Plaud, wants to convert lectures/recordings for transcription, or needs to batch-convert and merge media files with size/duration limits.
---

# Plaud Converter

Convert media files to MP3 for import into Plaud, with optional merge into chunks.

## Plaud import constraints

- **Supported formats**: MP3, MP4, WAV, OGG, RMVB, RM, DIVX, TS, M2TS, 3GP, F4V, ASR
- **Max file length**: 5 hours
- **Max file size**: 500 MB (target 490 MB for safety margin)

## How to convert

```bash
python3 convert.py <input_directory> [-o <output_directory>] [--max-size <MB>] [--merge] [--merge-prefix <name>] [-y]
```

### Convert only

```bash
python3 convert.py /path/to/lectures
```

### Convert and merge into chunks

```bash
python3 convert.py /path/to/lectures --merge --merge-prefix "course"
```

Merged files are saved to `<output>/merged/` as `<prefix>_part1.mp3`, `<prefix>_part2.mp3`, etc. Each chunk stays within 5 hours and 490 MB.

### Interactive mode (default)

If `--merge` is not passed and `-y` is not set, the script will ask the user after conversion whether they want to merge the files.

### What the script does

1. Recursively finds all video/audio files in the input directory
2. Skips macOS resource fork files (`._*`) and files over 5 hours
3. Calculates optimal bitrate to keep each file under 490 MB
4. Converts to MP3 using ffmpeg (audio only, no video)
5. Prefixes filenames with subfolder names to avoid naming conflicts
6. Optionally merges converted files into sequential chunks fitting Plaud limits

### Requirements

- Python 3.10+
- ffmpeg (`brew install ffmpeg`)
