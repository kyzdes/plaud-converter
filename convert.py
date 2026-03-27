#!/usr/bin/env python3
"""
Plaud Converter — converts video/audio files to MP3 for import into Plaud.

Plaud import constraints:
  - Supported formats: MP3, MP4, WAV, OGG, RMVB, RM, DIVX, TS, M2TS, 3GP, F4V, ASR
  - Max file length: 5 hours
  - Max file size: 500 MB

This script converts all media files in a directory (recursively) to MP3,
targeting < 490 MB per file. Files already under limits are converted at 128kbps.
Large files get a reduced bitrate to stay within the size limit.
"""

import argparse
import os
import subprocess
import sys

SUPPORTED_VIDEO = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".webm", ".m4v",
                   ".rmvb", ".rm", ".divx", ".ts", ".m2ts", ".3gp", ".f4v"}
SUPPORTED_AUDIO = {".mp3", ".wav", ".ogg", ".asr", ".m4a", ".flac", ".aac", ".wma"}
ALL_SUPPORTED = SUPPORTED_VIDEO | SUPPORTED_AUDIO

MAX_SIZE_MB = 490
MAX_DURATION_SEC = 5 * 3600  # 5 hours
DEFAULT_BITRATE = 128  # kbps


def get_duration(filepath: str) -> float | None:
    """Get media duration in seconds using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", filepath],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def calc_bitrate(duration_sec: float, max_size_mb: int = MAX_SIZE_MB) -> int:
    """Calculate max bitrate (kbps) to fit within size limit."""
    max_bits = max_size_mb * 1024 * 1024 * 8
    bitrate = int(max_bits / duration_sec / 1000)
    return min(bitrate, DEFAULT_BITRATE)


def find_media_files(input_dir: str, output_dir: str) -> list[str]:
    """Recursively find all media files, excluding the output directory."""
    files = []
    output_dir_abs = os.path.abspath(output_dir)
    for root, _, filenames in os.walk(input_dir):
        if os.path.abspath(root).startswith(output_dir_abs):
            continue
        for fn in filenames:
            if fn.startswith("._"):
                continue
            ext = os.path.splitext(fn)[1].lower()
            if ext in ALL_SUPPORTED:
                files.append(os.path.join(root, fn))
    files.sort()
    return files


def make_unique_name(filepath: str, input_dir: str) -> str:
    """Generate a unique output filename using the relative directory as prefix."""
    rel_dir = os.path.relpath(os.path.dirname(filepath), input_dir)
    rel_dir = rel_dir.replace(os.sep, "_")
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    if rel_dir == ".":
        return f"{base_name}.mp3"
    return f"{rel_dir}_{base_name}.mp3"


def convert(input_dir: str, output_dir: str, max_size_mb: int = MAX_SIZE_MB):
    """Convert all media files to MP3 for Plaud import."""
    os.makedirs(output_dir, exist_ok=True)
    files = find_media_files(input_dir, output_dir)

    if not files:
        print("No media files found.")
        return

    total = len(files)
    print(f"Found {total} media file(s)\n")

    errors = []
    for i, fpath in enumerate(files, 1):
        rel = os.path.relpath(fpath, input_dir)
        out_name = make_unique_name(fpath, input_dir)
        out_path = os.path.join(output_dir, out_name)

        duration = get_duration(fpath)
        if duration and duration > MAX_DURATION_SEC:
            print(f"[{i}/{total}] SKIP (>{MAX_DURATION_SEC/3600:.0f}h): {rel}")
            errors.append((rel, "exceeds 5 hour limit"))
            continue

        bitrate = calc_bitrate(duration, max_size_mb) if duration else DEFAULT_BITRATE

        print(f"[{i}/{total}] {rel} -> {out_name} ({bitrate}kbps)")

        result = subprocess.run(
            ["ffmpeg", "-i", fpath, "-vn", "-codec:a", "libmp3lame",
             "-b:a", f"{bitrate}k", "-y", out_path],
            capture_output=True, text=True
        )

        if result.returncode != 0:
            print(f"  ERROR: {result.stderr[-200:]}")
            errors.append((rel, "ffmpeg error"))
        else:
            size_mb = os.path.getsize(out_path) / (1024 * 1024)
            print(f"  OK ({size_mb:.1f} MB)")

    print(f"\nDone! {total - len(errors)}/{total} converted -> {output_dir}")
    if errors:
        print("\nFailed:")
        for name, reason in errors:
            print(f"  - {name}: {reason}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert media files to MP3 for Plaud import (max 490MB, max 5h)"
    )
    parser.add_argument("input_dir", help="Directory with media files (scanned recursively)")
    parser.add_argument("-o", "--output", help="Output directory (default: <input_dir>/converted)")
    parser.add_argument("--max-size", type=int, default=MAX_SIZE_MB,
                        help=f"Max output file size in MB (default: {MAX_SIZE_MB})")
    args = parser.parse_args()

    input_dir = os.path.abspath(args.input_dir)
    output_dir = args.output or os.path.join(input_dir, "converted")

    if not os.path.isdir(input_dir):
        print(f"Error: {input_dir} is not a directory")
        sys.exit(1)

    convert(input_dir, output_dir, args.max_size)


if __name__ == "__main__":
    main()
