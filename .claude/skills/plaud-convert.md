---
name: plaud-convert
description: Convert video/audio files to MP3 for Plaud import. Use when user mentions Plaud, wants to convert lectures/recordings for transcription, or needs to batch-convert media files with size limits.
---

# Plaud Converter

Convert media files to MP3 for import into Plaud.

## Plaud import constraints

- **Supported formats**: MP3, MP4, WAV, OGG, RMVB, RM, DIVX, TS, M2TS, 3GP, F4V, ASR
- **Max file length**: 5 hours
- **Max file size**: 500 MB (target 490 MB for safety margin)

## How to convert

Run the converter script:

```bash
python3 convert.py <input_directory> [-o <output_directory>] [--max-size <MB>]
```

### Examples

Convert all files in a folder (output goes to `<input>/converted/`):
```bash
python3 convert.py /path/to/lectures
```

Custom output directory:
```bash
python3 convert.py /path/to/lectures -o /path/to/output
```

### What the script does

1. Recursively finds all video/audio files in the input directory
2. Skips macOS resource fork files (`._*`)
3. Checks duration — skips files over 5 hours
4. Calculates optimal bitrate to keep each file under 490 MB
5. Converts to MP3 using ffmpeg (audio only, no video)
6. Prefixes filenames with subfolder names to avoid naming conflicts

### Requirements

- Python 3.10+
- ffmpeg (`brew install ffmpeg`)
