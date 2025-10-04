#!/bin/bash

# Quick progress checker for Archive.org downloads

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${CONFIG_FILE:-$SCRIPT_DIR/config.env}"

if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

# Set defaults if not defined in config
PDF_DIR="${PDF_DIR:-/home/jic823/projects/def-jic823/pdf}"
SUBJECT="${SUBJECT:-India -- Gazetteers}"
START_YEAR="${START_YEAR:-1815}"
END_YEAR="${END_YEAR:-1960}"
SLURM_USER="${SLURM_USER:-$USER}"

PROGRESS_FILE="$PDF_DIR/download_progress.json"
TARGET_QUERY="subject:\"$SUBJECT\" AND year:[$START_YEAR TO $END_YEAR]"

printf 'Archive.org Download Progress Check\n'
printf '==================================\n'
printf 'Directory: %s\n' "$PDF_DIR"
printf 'Time: %s\n\n' "$(date)"

# Count current PDFs
if [ -d "$PDF_DIR" ]; then
    pdf_count=$(find "$PDF_DIR" -name "*.pdf" | wc -l)
    printf 'Current PDF files: %s\n' "$pdf_count"
    printf 'Disk usage: %s\n' "$(du -sh "$PDF_DIR" | cut -f1)"
else
    printf 'PDF directory does not exist yet.\n'
    pdf_count=0
fi

printf '\n'

# Check progress file
if [ -f "$PROGRESS_FILE" ]; then
    printf 'Progress file details:\n'
    python3 - "$PROGRESS_FILE" "$TARGET_QUERY" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

progress_path = Path(sys.argv[1])
query = sys.argv[2] if len(sys.argv) > 2 else ""


def fetch_total_items(search_query: str):
    if not search_query:
        return None
    url = "https://archive.org/advancedsearch.php"
    params = {
        "q": search_query,
        "fl": "identifier",
        "rows": 0,
        "output": "json",
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get("response", {}).get("numFound")
    except Exception:
        return None


try:
    data = json.loads(progress_path.read_text())
except Exception as exc:
    print(f"Error reading progress file: {exc}")
else:
    downloaded = data.get("downloaded", 0)
    failed = data.get("failed", 0)
    skipped = data.get("skipped", 0)
    total_processed = downloaded + failed + skipped

    print(f"  Downloaded: {downloaded:,}")
    print(f"  Failed: {failed:,}")
    print(f"  Skipped: {skipped:,}")
    print(f"  Total processed: {total_processed:,}")
    success_rate = (downloaded / total_processed * 100) if total_processed else 0
    print(f"  Success rate: {success_rate:.1f}%")

    last_update = data.get("last_update", "")
    if last_update:
        try:
            dt = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
            print(f"  Last update: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception:
            print(f"  Last update: {last_update}")

    total_items = fetch_total_items(query)
    if total_items:
        percent_complete = (total_processed / total_items * 100) if total_processed else 0
        print(f"  Progress: {percent_complete:.1f}% of ~{total_items:,} total items")
        if downloaded:
            remaining = max(total_items - total_processed, 0)
            print(f"  Estimated remaining: {remaining:,} items")
    else:
        print("  Progress: unable to retrieve total item count right now")
PY
else
    printf 'No progress file found.\n'
fi

printf '\n'

# Check for running jobs
running_jobs=$(squeue -u "$SLURM_USER" --name=archive_download --noheader 2>/dev/null | wc -l)
if [ "$running_jobs" -gt 0 ]; then
    printf 'Running jobs:\n'
    squeue -u "$SLURM_USER" --name=archive_download
else
    printf 'No archive_download jobs currently running.\n'
fi

printf '\n'

# Show recent log entries if available
latest_log=$(ls -t "$PDF_DIR"/archive_download_*.out 2>/dev/null | head -1)
if [ -n "$latest_log" ]; then
    printf 'Recent log entries from: %s\n' "$(basename "$latest_log")"
    printf '----------------------------------------\n'
    tail -10 "$latest_log" 2>/dev/null || printf 'Could not read log file\n'
fi

printf '\n'
printf 'Target query: %s\n' "$TARGET_QUERY"
printf 'To restart/continue: ./restart_download.sh\n'
