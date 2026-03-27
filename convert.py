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

Optional merge mode: concatenates converted files into chunks fitting within
the 5-hour / 490 MB limits.
"""

import argparse
import os
import subprocess
import sys
import tempfile

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


def fmt_duration(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}:{m:02d}:{s:02d}"


def convert(input_dir: str, output_dir: str, max_size_mb: int = MAX_SIZE_MB) -> list[str]:
    """Convert all media files to MP3 for Plaud import. Returns list of converted file paths."""
    os.makedirs(output_dir, exist_ok=True)
    files = find_media_files(input_dir, output_dir)

    if not files:
        print("No media files found.")
        return []

    total = len(files)
    print(f"Found {total} media file(s)\n")

    converted = []
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
            converted.append(out_path)

    print(f"\nDone! {len(converted)}/{total} converted -> {output_dir}")
    if errors:
        print("\nFailed:")
        for name, reason in errors:
            print(f"  - {name}: {reason}")

    return converted


def plan_merge_chunks(files: list[str], max_duration: float, max_size_mb: int) -> list[list[str]]:
    """Split files into chunks that fit within duration and size limits."""
    chunks: list[list[str]] = []
    current_chunk: list[str] = []
    current_duration = 0.0
    current_size_mb = 0.0

    for fpath in files:
        duration = get_duration(fpath) or 0
        size_mb = os.path.getsize(fpath) / (1024 * 1024)

        if current_chunk and (current_duration + duration > max_duration
                              or current_size_mb + size_mb > max_size_mb):
            chunks.append(current_chunk)
            current_chunk = []
            current_duration = 0.0
            current_size_mb = 0.0

        current_chunk.append(fpath)
        current_duration += duration
        current_size_mb += size_mb

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def merge_files(files: list[str], output_dir: str, prefix: str = "merged",
                max_size_mb: int = MAX_SIZE_MB):
    """Merge converted MP3 files into chunks fitting Plaud limits."""
    if not files:
        print("No files to merge.")
        return

    # Gather durations for summary
    file_info = []
    total_duration = 0.0
    total_size = 0.0
    for f in files:
        dur = get_duration(f) or 0
        size = os.path.getsize(f) / (1024 * 1024)
        file_info.append((f, dur, size))
        total_duration += dur
        total_size += size

    print(f"\nMerge: {len(files)} files, "
          f"total duration {fmt_duration(total_duration)}, "
          f"total size {total_size:.0f} MB")

    chunks = plan_merge_chunks(files, MAX_DURATION_SEC, max_size_mb)
    print(f"Will produce {len(chunks)} merged file(s)\n")

    merged_dir = os.path.join(output_dir, "merged")
    os.makedirs(merged_dir, exist_ok=True)

    for i, chunk in enumerate(chunks, 1):
        chunk_duration = sum(get_duration(f) or 0 for f in chunk)
        chunk_size = sum(os.path.getsize(f) / (1024 * 1024) for f in chunk)
        out_path = os.path.join(merged_dir, f"{prefix}_part{i}.mp3")

        print(f"[Part {i}/{len(chunks)}] {len(chunk)} files, "
              f"{fmt_duration(chunk_duration)}, ~{chunk_size:.0f} MB")

        # Create concat list file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            for f in chunk:
                tmp.write(f"file '{f}'\n")
            list_path = tmp.name

        try:
            result = subprocess.run(
                ["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_path,
                 "-c", "copy", "-y", out_path],
                capture_output=True, text=True
            )

            if result.returncode != 0:
                # Fallback: re-encode if concat copy fails (mixed formats/params)
                result = subprocess.run(
                    ["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_path,
                     "-codec:a", "libmp3lame", "-b:a", "128k", "-y", out_path],
                    capture_output=True, text=True
                )

            if result.returncode != 0:
                print(f"  ERROR: {result.stderr[-200:]}")
            else:
                final_size = os.path.getsize(out_path) / (1024 * 1024)
                final_dur = get_duration(out_path) or 0
                print(f"  OK -> {os.path.basename(out_path)} "
                      f"({fmt_duration(final_dur)}, {final_size:.1f} MB)")
        finally:
            os.unlink(list_path)

    print(f"\nMerged files saved to: {merged_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert media files to MP3 for Plaud import (max 490MB, max 5h)"
    )
    parser.add_argument("input_dir", help="Directory with media files (scanned recursively)")
    parser.add_argument("-o", "--output", help="Output directory (default: <input_dir>/converted)")
    parser.add_argument("--max-size", type=int, default=MAX_SIZE_MB,
                        help=f"Max output file size in MB (default: {MAX_SIZE_MB})")
    parser.add_argument("--merge", action="store_true",
                        help="Merge converted files into chunks fitting Plaud limits")
    parser.add_argument("--merge-prefix", default="merged",
                        help="Prefix for merged filenames (default: 'merged')")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Skip interactive prompts")
    args = parser.parse_args()

    input_dir = os.path.abspath(args.input_dir)
    output_dir = args.output or os.path.join(input_dir, "converted")

    if not os.path.isdir(input_dir):
        print(f"Error: {input_dir} is not a directory")
        sys.exit(1)

    converted = convert(input_dir, output_dir, args.max_size)

    if not converted:
        return

    if args.merge:
        merge_files(converted, output_dir, args.merge_prefix, args.max_size)
    elif not args.yes:
        print()
        answer = input("Merge converted files into chunks for Plaud? [y/N] ").strip().lower()
        if answer in ("y", "yes", "д", "да"):
            merge_prefix = input("Prefix for merged files [merged]: ").strip() or "merged"
            merge_files(converted, output_dir, merge_prefix, args.max_size)


if __name__ == "__main__":
    main()
