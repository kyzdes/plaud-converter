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

Merge mode: concatenates files per source folder (1 folder = 1 topic/lecture).
If a folder exceeds 5h/490MB, it splits into numbered parts.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from collections import OrderedDict

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


def natural_sort_key(path: str):
    """Sort key that handles numbers naturally: 1, 2, 10 instead of 1, 10, 2."""
    parts = re.split(r'(\d+)', path)
    return [int(p) if p.isdigit() else p.lower() for p in parts]


def find_media_files(input_dir: str, output_dir: str) -> list[str]:
    """Recursively find all media files, excluding the output directory.
    Uses natural sorting so files are ordered 1, 2, 3, ..., 10, 11 (not 1, 10, 11, 2)."""
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
    files.sort(key=natural_sort_key)
    return files


def group_by_source_folder(files: list[str], input_dir: str) -> OrderedDict:
    """Group converted files by their source folder.
    Converted files are named as '<folder>_<filename>.mp3'.
    Returns OrderedDict[folder_name -> list[filepath]] in natural sort order."""
    groups = {}
    for fpath in files:
        basename = os.path.basename(fpath)
        # Extract folder prefix: everything before the last '_' that matches a known folder
        # The naming convention is: <folder>_<original_name>.mp3
        # For root-level files (no folder prefix): folder = "root"
        parts = basename.split("_", 1)
        if len(parts) == 2:
            folder = parts[0]
        else:
            folder = "root"
        if folder not in groups:
            groups[folder] = []
        groups[folder].append(fpath)

    # Sort groups by folder name naturally, and files within each group
    sorted_groups = OrderedDict()
    for key in sorted(groups.keys(), key=natural_sort_key):
        sorted_groups[key] = sorted(groups[key], key=lambda f: natural_sort_key(os.path.basename(f)))

    return sorted_groups


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


def plan_folder_chunks(files: list[str], max_duration: float, max_size_mb: int) -> list[list[str]]:
    """Split a single folder's files into chunks that fit within duration and size limits."""
    chunks = []
    current_chunk = []
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


def concat_chunk(chunk: list[str], out_path: str) -> bool:
    """Concatenate a list of MP3 files into one. Returns True on success."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        for f in chunk:
            tmp.write(f"file '{f}'\n")
        list_path = tmp.name

    try:
        # Try lossless concat first
        result = subprocess.run(
            ["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_path,
             "-c", "copy", "-y", out_path],
            capture_output=True, text=True
        )

        if result.returncode != 0:
            # Fallback: re-encode
            result = subprocess.run(
                ["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_path,
                 "-codec:a", "libmp3lame", "-b:a", "128k", "-y", out_path],
                capture_output=True, text=True
            )

        if result.returncode != 0:
            print(f"  ERROR: {result.stderr[-200:]}")
            return False
        return True
    finally:
        os.unlink(list_path)


def merge_by_folder(files: list[str], input_dir: str, output_dir: str,
                    max_size_mb: int = MAX_SIZE_MB):
    """Merge converted files grouped by source folder.
    1 folder = 1 merged file (= 1 topic/lecture).
    If a folder exceeds limits, splits into parts."""
    if not files:
        print("No files to merge.")
        return

    groups = group_by_source_folder(files, input_dir)

    total_files = sum(len(v) for v in groups.values())
    print(f"\nMerge by folder: {total_files} files across {len(groups)} folder(s)")

    merged_dir = os.path.join(output_dir, "merged")
    os.makedirs(merged_dir, exist_ok=True)

    merged_count = 0
    for folder_name, folder_files in groups.items():
        folder_dur = sum(get_duration(f) or 0 for f in folder_files)
        folder_size = sum(os.path.getsize(f) / (1024 * 1024) for f in folder_files)

        print(f"\n[{folder_name}] {len(folder_files)} files, "
              f"{fmt_duration(folder_dur)}, {folder_size:.0f} MB")

        chunks = plan_folder_chunks(folder_files, MAX_DURATION_SEC, max_size_mb)

        for ci, chunk in enumerate(chunks):
            chunk_dur = sum(get_duration(f) or 0 for f in chunk)
            chunk_size = sum(os.path.getsize(f) / (1024 * 1024) for f in chunk)

            if len(chunks) == 1:
                out_name = f"{folder_name}.mp3"
            else:
                out_name = f"{folder_name}_part{ci + 1}.mp3"

            out_path = os.path.join(merged_dir, out_name)

            if len(chunk) == 1:
                # Single file — just copy
                import shutil
                shutil.copy2(chunk[0], out_path)
                ok = True
            else:
                ok = concat_chunk(chunk, out_path)

            if ok:
                final_dur = get_duration(out_path) or 0
                final_size = os.path.getsize(out_path) / (1024 * 1024)
                part_label = f" (part {ci + 1}/{len(chunks)})" if len(chunks) > 1 else ""
                print(f"  -> {out_name}{part_label}: "
                      f"{fmt_duration(final_dur)}, {final_size:.1f} MB")
                merged_count += 1

    print(f"\nMerged {merged_count} file(s) -> {merged_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert media files to MP3 for Plaud import (max 490MB, max 5h)"
    )
    parser.add_argument("input_dir", help="Directory with media files (scanned recursively)")
    parser.add_argument("-o", "--output", help="Output directory (default: <input_dir>/converted)")
    parser.add_argument("--max-size", type=int, default=MAX_SIZE_MB,
                        help=f"Max output file size in MB (default: {MAX_SIZE_MB})")
    parser.add_argument("--merge", action="store_true",
                        help="Merge converted files by folder (1 folder = 1 topic)")
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
        merge_by_folder(converted, input_dir, output_dir, args.max_size)
    elif not args.yes:
        print()
        answer = input("Merge files by folder (1 folder = 1 topic)? [y/N] ").strip().lower()
        if answer in ("y", "yes", "д", "да"):
            merge_by_folder(converted, input_dir, output_dir, args.max_size)


if __name__ == "__main__":
    main()
