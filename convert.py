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

Report mode: generates an HTML report with full conversion statistics.
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import webbrowser
from collections import OrderedDict
from datetime import datetime

SUPPORTED_VIDEO = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".webm", ".m4v",
                   ".rmvb", ".rm", ".divx", ".ts", ".m2ts", ".3gp", ".f4v"}
SUPPORTED_AUDIO = {".mp3", ".wav", ".ogg", ".asr", ".m4a", ".flac", ".aac", ".wma"}
ALL_SUPPORTED = SUPPORTED_VIDEO | SUPPORTED_AUDIO

MAX_SIZE_MB = 490
MAX_DURATION_SEC = 5 * 3600  # 5 hours
DEFAULT_BITRATE = 128  # kbps


# ─── Utilities ───────────────────────────────────────────────────────────────

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


def fmt_duration(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}:{m:02d}:{s:02d}"


def fmt_size(mb: float) -> str:
    """Format megabytes as human-readable string."""
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB"
    return f"{mb:.1f} MB"


# ─── File discovery ──────────────────────────────────────────────────────────

def find_media_files(input_dir: str, output_dir: str) -> list[str]:
    """Recursively find all media files, excluding the output directory.
    Uses natural sorting so files are ordered 1, 2, 3, ..., 10, 11."""
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
    """Group converted files by their source folder prefix.
    Returns OrderedDict[folder_name -> list[filepath]] in natural sort order."""
    groups = {}
    for fpath in files:
        basename = os.path.basename(fpath)
        parts = basename.split("_", 1)
        folder = parts[0] if len(parts) == 2 else "root"
        if folder not in groups:
            groups[folder] = []
        groups[folder].append(fpath)

    sorted_groups = OrderedDict()
    for key in sorted(groups.keys(), key=natural_sort_key):
        sorted_groups[key] = sorted(
            groups[key], key=lambda f: natural_sort_key(os.path.basename(f)))
    return sorted_groups


def make_unique_name(filepath: str, input_dir: str) -> str:
    """Generate a unique output filename using the relative directory as prefix."""
    rel_dir = os.path.relpath(os.path.dirname(filepath), input_dir)
    rel_dir = rel_dir.replace(os.sep, "_")
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    if rel_dir == ".":
        return f"{base_name}.mp3"
    return f"{rel_dir}_{base_name}.mp3"


# ─── Conversion ──────────────────────────────────────────────────────────────

def convert(input_dir: str, output_dir: str,
            max_size_mb: int = MAX_SIZE_MB) -> tuple[list[dict], list[dict]]:
    """Convert all media files to MP3. Returns (source_log, converted_log)."""
    os.makedirs(output_dir, exist_ok=True)
    files = find_media_files(input_dir, output_dir)

    if not files:
        print("No media files found.")
        return [], []

    total = len(files)
    print(f"Found {total} media file(s)\n")

    source_log = []
    converted_log = []
    errors = []

    for i, fpath in enumerate(files, 1):
        rel = os.path.relpath(fpath, input_dir)
        folder = os.path.relpath(os.path.dirname(fpath), input_dir)
        fname = os.path.basename(fpath)
        out_name = make_unique_name(fpath, input_dir)
        out_path = os.path.join(output_dir, out_name)

        duration = get_duration(fpath) or 0
        src_size = os.path.getsize(fpath) / (1024 * 1024)

        source_log.append({
            "folder": folder, "name": fname,
            "size_mb": round(src_size, 1),
            "dur": duration, "dur_fmt": fmt_duration(duration),
        })

        if duration > MAX_DURATION_SEC:
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
            out_size = os.path.getsize(out_path) / (1024 * 1024)
            out_dur = get_duration(out_path) or 0
            print(f"  OK ({out_size:.1f} MB)")

            parts = out_name.split("_", 1)
            conv_folder = parts[0] if len(parts) == 2 else "root"
            converted_log.append({
                "name": out_name, "path": out_path, "folder": conv_folder,
                "size_mb": round(out_size, 1),
                "dur": out_dur, "dur_fmt": fmt_duration(out_dur),
            })

    print(f"\nDone! {len(converted_log)}/{total} converted -> {output_dir}")
    if errors:
        print("\nFailed:")
        for name, reason in errors:
            print(f"  - {name}: {reason}")

    return source_log, converted_log


# ─── Merging ─────────────────────────────────────────────────────────────────

def plan_folder_chunks(files: list[str], max_duration: float,
                       max_size_mb: int) -> list[list[str]]:
    """Split a single folder's files into chunks fitting duration and size limits."""
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
        result = subprocess.run(
            ["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_path,
             "-c", "copy", "-y", out_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
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


def merge_by_folder(converted_log: list[dict], input_dir: str, output_dir: str,
                    max_size_mb: int = MAX_SIZE_MB) -> list[dict]:
    """Merge converted files grouped by source folder.
    1 folder = 1 merged file (= 1 topic/lecture).
    Returns merged_log list."""
    files = [c["path"] for c in converted_log]
    if not files:
        print("No files to merge.")
        return []

    groups = group_by_source_folder(files, input_dir)

    total_files = sum(len(v) for v in groups.values())
    print(f"\nMerge by folder: {total_files} files across {len(groups)} folder(s)")

    merged_dir = os.path.join(output_dir, "merged")
    os.makedirs(merged_dir, exist_ok=True)

    merged_log = []
    for folder_name, folder_files in groups.items():
        folder_dur = sum(get_duration(f) or 0 for f in folder_files)
        folder_size = sum(os.path.getsize(f) / (1024 * 1024) for f in folder_files)

        print(f"\n[{folder_name}] {len(folder_files)} files, "
              f"{fmt_duration(folder_dur)}, {folder_size:.0f} MB")

        chunks = plan_folder_chunks(folder_files, MAX_DURATION_SEC, max_size_mb)

        for ci, chunk in enumerate(chunks):
            if len(chunks) == 1:
                out_name = f"{folder_name}.mp3"
            else:
                out_name = f"{folder_name}_part{ci + 1}.mp3"

            out_path = os.path.join(merged_dir, out_name)

            if len(chunk) == 1:
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
                merged_log.append({
                    "name": out_name,
                    "size_mb": round(final_size, 1),
                    "dur": final_dur,
                    "dur_fmt": fmt_duration(final_dur),
                })

    print(f"\nMerged {len(merged_log)} file(s) -> {merged_dir}")
    return merged_log


# ─── HTML Report ─────────────────────────────────────────────────────────────

def generate_report(source_log: list[dict], converted_log: list[dict],
                    merged_log: list[dict], output_dir: str,
                    convert_time: float, open_browser: bool = True) -> str:
    """Generate an HTML report with full conversion statistics.
    Returns the path to the report file."""

    # Stats
    folders = sorted(set(s["folder"] for s in source_log), key=natural_sort_key)
    src_sz = sum(s["size_mb"] for s in source_log)
    src_dur = sum(s["dur"] for s in source_log)
    conv_sz = sum(c["size_mb"] for c in converted_log)
    conv_dur = sum(c["dur"] for c in converted_log)
    mrg_sz = sum(m["size_mb"] for m in merged_log)
    mrg_dur = sum(m["dur"] for m in merged_log)
    compression = src_sz / conv_sz if conv_sz else 0

    # Per-folder stats
    folder_stats = {}
    for s in source_log:
        f = s["folder"]
        if f not in folder_stats:
            folder_stats[f] = {"files": 0, "size_mb": 0.0, "dur": 0.0}
        folder_stats[f]["files"] += 1
        folder_stats[f]["size_mb"] += s["size_mb"]
        folder_stats[f]["dur"] += s["dur"]

    now = datetime.now()
    match_class = "g" if len(merged_log) >= len(folders) else "r"
    match_label = "Match!" if len(merged_log) >= len(folders) else "Mismatch"

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Plaud Converter Report</title>
<style>
:root {{
  --bg:#0f1117;--s1:#1a1d27;--s2:#232735;--bd:#2d3140;
  --t1:#e4e6ef;--t2:#8b8fa3;--ac:#6c5ce7;--ac2:#a29bfe;
  --g:#00b894;--o:#fdcb6e;--r:#ff7675;--b:#74b9ff;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',sans-serif;background:var(--bg);color:var(--t1);line-height:1.6;padding:2rem}}
.c{{max-width:1200px;margin:0 auto}}
h1{{font-size:1.8rem;font-weight:700;margin-bottom:.3rem;background:linear-gradient(135deg,var(--ac2),var(--b));-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.sub{{color:var(--t2);font-size:.9rem;margin-bottom:2rem}}
.sg{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin-bottom:2.5rem}}
.sc{{background:var(--s1);border:1px solid var(--bd);border-radius:12px;padding:1.2rem}}
.sc .l{{color:var(--t2);font-size:.75rem;text-transform:uppercase;letter-spacing:.05em}}
.sc .v{{font-size:1.5rem;font-weight:700;margin-top:.2rem}}
.sc .s{{color:var(--t2);font-size:.82rem}}
.sc.g .v{{color:var(--g)}}.sc.o .v{{color:var(--o)}}.sc.b .v{{color:var(--b)}}.sc.a .v{{color:var(--ac2)}}.sc.r .v{{color:var(--r)}}
.sec{{margin-bottom:2.5rem}}
.sec h2{{font-size:1.15rem;font-weight:600;margin-bottom:1rem;padding-bottom:.5rem;border-bottom:1px solid var(--bd)}}
table{{width:100%;border-collapse:collapse;font-size:.85rem}}
th{{text-align:left;padding:.6rem .8rem;color:var(--t2);font-weight:500;font-size:.75rem;text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid var(--bd);position:sticky;top:0;background:var(--s1)}}
td{{padding:.5rem .8rem;border-bottom:1px solid var(--bd)}}
tr:hover td{{background:var(--s2)}}
.tw{{background:var(--s1);border:1px solid var(--bd);border-radius:12px;overflow:hidden;max-height:500px;overflow-y:auto}}
.n{{font-variant-numeric:tabular-nums;text-align:right;color:var(--t2)}}
.ft{{display:inline-block;background:var(--s2);border:1px solid var(--bd);border-radius:4px;padding:.1rem .45rem;font-size:.75rem;color:var(--ac2);margin-right:.3rem}}
.mc{{background:linear-gradient(135deg,rgba(108,92,231,.08),rgba(116,185,255,.08));border:1px solid rgba(108,92,231,.25);border-radius:12px;padding:1.2rem;margin-bottom:.8rem}}
.mc .pn{{font-weight:600;color:var(--ac2);font-size:1rem}}.mc .mt{{color:var(--t2);font-size:.85rem;margin-top:.2rem}}
.mg{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:.8rem}}
.bc{{width:100%;height:6px;background:var(--s2);border-radius:3px;overflow:hidden;margin-top:.3rem}}
.b{{height:100%;border-radius:3px;background:var(--ac)}}
.b.w{{background:var(--o)}}.b.d{{background:var(--r)}}
.row{{display:flex;gap:.8rem;align-items:center;margin-top:.3rem}}
.row span{{font-size:.72rem;color:var(--t2)}}
.row .lb{{width:55px}}
.footer{{text-align:center;color:var(--t2);font-size:.78rem;margin-top:3rem;padding-top:1.5rem;border-top:1px solid var(--bd)}}
.match{{background:rgba(0,184,148,.08);border:1px solid rgba(0,184,148,.2);border-radius:8px;padding:.8rem 1rem;margin-top:1rem;font-size:.85rem;color:var(--g)}}
</style>
</head>
<body>
<div class="c">

<h1>Plaud Converter Report</h1>
<p class="sub">{now.strftime("%d.%m.%Y %H:%M")} &middot; {convert_time:.0f}s</p>

<div class="sg">
  <div class="sc a"><div class="l">Source</div><div class="v">{len(source_log)}</div><div class="s">{len(folders)} folders</div></div>
  <div class="sc o"><div class="l">Source size</div><div class="v">{fmt_size(src_sz)}</div><div class="s">{fmt_duration(src_dur)}</div></div>
  <div class="sc g"><div class="l">Converted</div><div class="v">{len(converted_log)}</div><div class="s">{fmt_size(conv_sz)} / {fmt_duration(conv_dur)}</div></div>
  <div class="sc b"><div class="l">Compression</div><div class="v">{compression:.1f}x</div><div class="s">{fmt_size(src_sz)} &rarr; {fmt_size(conv_sz)}</div></div>
  <div class="sc a"><div class="l">Merged</div><div class="v">{len(merged_log)}</div><div class="s">{fmt_size(mrg_sz)} / {fmt_duration(mrg_dur)}</div></div>
  <div class="sc {match_class}"><div class="l">Folders vs Merged</div><div class="v">{len(folders)} &rarr; {len(merged_log)}</div><div class="s">{match_label}</div></div>
</div>
"""

    if len(merged_log) >= len(folders):
        html += '<div class="match">1 folder = 1 merged file. All topics preserved for Plaud analytics.</div>\n'

    # ── Merged files ──
    if merged_log:
        html += '<div class="sec"><h2>Merged Files (1 per topic)</h2><div class="mg">\n'
        for m in merged_log:
            pd = min(m["dur"] / (5 * 3600) * 100, 100)
            ps = min(m["size_mb"] / 490 * 100, 100)
            bc = "d" if pd > 90 else ("w" if pd > 70 else "")
            html += f'''<div class="mc">
  <div class="pn">{m["name"]}</div>
  <div class="mt">{m["dur_fmt"]} &middot; {fmt_size(m["size_mb"])}</div>
  <div class="row"><span class="lb">Duration</span><div class="bc" style="flex:1"><div class="b {bc}" style="width:{pd:.0f}%"></div></div><span>{pd:.0f}%</span></div>
  <div class="row"><span class="lb">Size</span><div class="bc" style="flex:1"><div class="b" style="width:{ps:.0f}%"></div></div><span>{ps:.0f}%</span></div>
</div>\n'''
        html += '</div></div>\n'

    # ── Folder breakdown ──
    html += '<div class="sec"><h2>Source Folders</h2><div class="tw"><table>\n'
    html += '<thead><tr><th>#</th><th>Folder</th><th class="n">Files</th><th class="n">Size</th><th class="n">Duration</th></tr></thead><tbody>\n'
    for i, f in enumerate(folders, 1):
        st = folder_stats[f]
        html += (f'<tr><td class="n">{i}</td><td><span class="ft">{f}</span></td>'
                 f'<td class="n">{st["files"]}</td><td class="n">{st["size_mb"]:.0f} MB</td>'
                 f'<td class="n">{fmt_duration(st["dur"])}</td></tr>\n')
    html += (f'<tr style="font-weight:600;border-top:2px solid var(--bd)">'
             f'<td></td><td>Total</td><td class="n">{len(source_log)}</td>'
             f'<td class="n">{fmt_size(src_sz)}</td><td class="n">{fmt_duration(src_dur)}</td></tr>\n')
    html += '</tbody></table></div></div>\n'

    # ── Source files ──
    html += '<div class="sec"><h2>All Source Files</h2><div class="tw"><table>\n'
    html += '<thead><tr><th>#</th><th>Folder</th><th>File</th><th class="n">Size</th><th class="n">Duration</th></tr></thead><tbody>\n'
    for i, s in enumerate(source_log, 1):
        html += (f'<tr><td class="n">{i}</td><td><span class="ft">{s["folder"]}</span></td>'
                 f'<td>{s["name"]}</td><td class="n">{s["size_mb"]} MB</td>'
                 f'<td class="n">{s["dur_fmt"]}</td></tr>\n')
    html += '</tbody></table></div></div>\n'

    # ── Converted files ──
    html += '<div class="sec"><h2>Converted Files</h2><div class="tw"><table>\n'
    html += '<thead><tr><th>#</th><th>Folder</th><th>File</th><th class="n">Size</th><th class="n">Duration</th></tr></thead><tbody>\n'
    for i, c in enumerate(converted_log, 1):
        html += (f'<tr><td class="n">{i}</td><td><span class="ft">{c["folder"]}</span></td>'
                 f'<td>{c["name"]}</td><td class="n">{c["size_mb"]} MB</td>'
                 f'<td class="n">{c["dur_fmt"]}</td></tr>\n')
    html += '</tbody></table></div></div>\n'

    html += (f'<div class="footer">Generated by plaud-converter &middot; '
             f'{now.strftime("%Y-%m-%d %H:%M:%S")}</div>\n')
    html += '</div></body></html>'

    report_path = os.path.join(output_dir, "report.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nReport: {report_path}")

    if open_browser:
        webbrowser.open(f"file://{os.path.abspath(report_path)}")

    return report_path


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Convert media files to MP3 for Plaud import (max 490MB, max 5h)"
    )
    parser.add_argument("input_dir",
                        help="Directory with media files (scanned recursively)")
    parser.add_argument("-o", "--output",
                        help="Output directory (default: <input_dir>/converted)")
    parser.add_argument("--max-size", type=int, default=MAX_SIZE_MB,
                        help=f"Max output file size in MB (default: {MAX_SIZE_MB})")
    parser.add_argument("--merge", action="store_true",
                        help="Merge converted files by folder (1 folder = 1 topic)")
    parser.add_argument("--report", action="store_true",
                        help="Generate HTML report after conversion")
    parser.add_argument("--no-open", action="store_true",
                        help="Don't open the report in browser")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Skip interactive prompts")
    args = parser.parse_args()

    input_dir = os.path.abspath(args.input_dir)
    output_dir = args.output or os.path.join(input_dir, "converted")

    if not os.path.isdir(input_dir):
        print(f"Error: {input_dir} is not a directory")
        sys.exit(1)

    t_start = time.time()
    source_log, converted_log = convert(input_dir, output_dir, args.max_size)

    if not converted_log:
        return

    merged_log = []

    if args.merge:
        merged_log = merge_by_folder(
            converted_log, input_dir, output_dir, args.max_size)
    elif not args.yes:
        print()
        answer = input(
            "Merge files by folder (1 folder = 1 topic)? [y/N] ").strip().lower()
        if answer in ("y", "yes", "д", "да"):
            merged_log = merge_by_folder(
                converted_log, input_dir, output_dir, args.max_size)

    convert_time = time.time() - t_start

    # Report: generate if --report, or ask interactively
    should_report = args.report
    if not should_report and not args.yes:
        print()
        answer = input("Generate HTML report? [y/N] ").strip().lower()
        should_report = answer in ("y", "yes", "д", "да")

    if should_report:
        generate_report(
            source_log, converted_log, merged_log,
            output_dir, convert_time,
            open_browser=not args.no_open,
        )


if __name__ == "__main__":
    main()
