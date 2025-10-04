#!/bin/bash

# Restart script for Archive.org downloads
# This script checks progress and resubmits the job if needed

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${CONFIG_FILE:-$SCRIPT_DIR/config.env}"

if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
else
    echo "Warning: Config file not found at $CONFIG_FILE"
    echo "Using default values. Copy config.env.example to config.env to customize."
fi

# Set defaults if not defined in config
PROJECT_DIR="${PROJECT_DIR:-/home/jic823/projects/def-jic823/InternetArchive}"
PDF_DIR="${PDF_DIR:-/home/jic823/projects/def-jic823/pdf}"
RUN_SCRIPT="${RUN_SCRIPT:-$PROJECT_DIR/run_archive_download.sh}"
SUBJECT="${SUBJECT:-India -- Gazetteers}"
START_YEAR="${START_YEAR:-1815}"
END_YEAR="${END_YEAR:-1960}"
SLURM_USER="${SLURM_USER:-$USER}"

PROGRESS_FILE="$PDF_DIR/download_progress.json"
TARGET_QUERY="subject:\"$SUBJECT\" AND year:[$START_YEAR TO $END_YEAR]"

echo "Archive.org Download Restart Script"
echo "=================================="

# Check if progress file exists
if [ -f "$PROGRESS_FILE" ]; then
    echo "Found progress file:"
    cat "$PROGRESS_FILE"
    echo ""

    # Count downloaded PDFs
    pdf_count=$(find "$PDF_DIR" -name "*.pdf" | wc -l)
    echo "Current PDF count: $pdf_count"

    # Activate virtual environment for Python script
    VENV_DIR="${VENV_DIR:-$PROJECT_DIR/venv}"
    if [ -d "$VENV_DIR" ]; then
        source "$VENV_DIR/bin/activate"
    fi

    python3 - "$PROGRESS_FILE" "$TARGET_QUERY" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

progress_path = Path(sys.argv[1])
query = sys.argv[2]


def fetch_total_items(search_query):
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
    print(f"Error reading progress: {exc}")
else:
    downloaded = data.get("downloaded", 0)
    failed = data.get("failed", 0)
    skipped = data.get("skipped", 0)
    total_processed = downloaded + failed + skipped

    print(f"Downloaded: {downloaded}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")
    print(f"Total processed: {total_processed}")

    last_update = data.get("last_update")
    if last_update:
        try:
            dt = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
            print(f"Last update: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception:
            print(f"Last update: {last_update}")

    total_items = fetch_total_items(query)
    if total_items:
        print(f"Estimated total items for query: {total_items}")
        remaining = max(total_items - total_processed, 0)
        print(f"Estimated remaining: {remaining}")
    else:
        print("Could not retrieve current total items from Archive.org")
PY
else
    echo "No progress file found. This appears to be a fresh start."
    pdf_count=$(find "$PDF_DIR" -name "*.pdf" 2>/dev/null | wc -l)
    echo "Current PDF count: $pdf_count"
fi

echo ""
echo "Target query: $TARGET_QUERY"

# Check if there are any running jobs
running_jobs=$(squeue -u "$SLURM_USER" --name=archive_download --noheader 2>/dev/null | wc -l)

if [ "$running_jobs" -gt 0 ]; then
    echo ""
    echo "Found $running_jobs running archive_download job(s):"
    squeue -u "$SLURM_USER" --name=archive_download
    echo ""
    read -p "Cancel running jobs and restart? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelling running jobs..."
        scancel -u "$SLURM_USER" --name=archive_download
        sleep 5
    else
        echo "Keeping existing jobs running. Exiting."
        exit 0
    fi
fi

echo ""
read -p "Submit new download job? (Y/n): " -n 1 -r
echo

if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo "Cancelled."
    exit 0
fi

if [ ! -x "$RUN_SCRIPT" ]; then
    echo "Run script not found or not executable: $RUN_SCRIPT"
    exit 1
fi

# Submit the job
echo "Submitting new archive download job..."
job_id=$(sbatch "$RUN_SCRIPT" | awk '{print $4}')

if [ $? -eq 0 ] && [ -n "$job_id" ]; then
    echo "Job submitted successfully: $job_id"
    echo ""
    echo "Monitor with:"
    echo "  squeue -j $job_id"
    echo "  tail -f $PDF_DIR/archive_download_${job_id}.out"
    echo ""
    echo "Check progress with:"
    echo "  ./check_progress.sh"
else
    echo "Failed to submit job!"
    exit 1
fi
