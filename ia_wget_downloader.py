#!/usr/bin/env python3
"""
Simple Internet Archive bulk downloader using wget.

Fetches all identifiers from IA search, then generates wget commands
for efficient bulk downloading.
"""

import argparse
import json
import requests
import subprocess
import sys
from pathlib import Path


def fetch_all_identifiers(query, output_format="json"):
    """Fetch all identifiers from Internet Archive search."""
    base_url = "https://archive.org/advancedsearch.php"

    # First, get total count
    params = {
        "q": query,
        "fl": "identifier",
        "rows": 1,
        "output": output_format
    }

    response = requests.get(base_url, params=params)
    response.raise_for_status()

    if output_format == "json":
        data = response.json()
        total = data["response"]["numFound"]
        print(f"Found {total} items matching query: {query}")

        # Now fetch all identifiers
        params["rows"] = total
        response = requests.get(base_url, params=params)
        response.raise_for_status()

        data = response.json()
        identifiers = [doc["identifier"] for doc in data["response"]["docs"]]
        return identifiers
    else:
        # Handle CSV format
        lines = response.text.strip().split('\n')
        if len(lines) < 2:
            return []
        return [line.strip().strip('"') for line in lines[1:] if line.strip()]


def generate_pdf_urls(identifiers, output_file="download_urls.txt"):
    """Generate PDF download URLs for wget."""
    urls = []

    for identifier in identifiers:
        # Most common PDF patterns for IA items
        pdf_urls = [
            f"https://archive.org/download/{identifier}/{identifier}.pdf",
            f"https://archive.org/download/{identifier}/{identifier}_text.pdf",
            f"https://archive.org/download/{identifier}/{identifier}_bw.pdf"
        ]
        urls.extend(pdf_urls)

    with open(output_file, 'w') as f:
        for url in urls:
            f.write(f"{url}\n")

    print(f"Generated {len(urls)} potential PDF URLs in {output_file}")
    return output_file


def create_wget_script(url_file, download_dir="./pdfs", script_name="download_pdfs.sh"):
    """Create wget download script."""

    script_content = f'''#!/bin/bash

# Internet Archive PDF bulk downloader using wget
# Generated from: {url_file}

DOWNLOAD_DIR="{download_dir}"
URL_FILE="{url_file}"

# Create download directory
mkdir -p "$DOWNLOAD_DIR"

echo "Starting bulk download to $DOWNLOAD_DIR"
echo "URLs from: $URL_FILE"
echo "Started at: $(date)"

# wget options:
# -i: read URLs from file
# -P: download to directory
# -c: continue partial downloads
# -t3: retry 3 times on failure
# --wait=0.1: wait 0.1s between downloads
# -T30: timeout after 30s
# --no-check-certificate: skip SSL checks if needed
# -q: quiet mode (less verbose)
# --show-progress: show progress bar

wget \\
    -i "$URL_FILE" \\
    -P "$DOWNLOAD_DIR" \\
    -c \\
    -t3 \\
    --wait=0.1 \\
    -T30 \\
    --show-progress \\
    --no-check-certificate \\
    2>&1 | tee wget_download.log

echo "Completed at: $(date)"
echo "Check wget_download.log for details"

# Count successful downloads
successful=$(find "$DOWNLOAD_DIR" -name "*.pdf" -type f | wc -l)
echo "Successfully downloaded: $successful PDF files"
'''

    with open(script_name, 'w') as f:
        f.write(script_content)

    # Make executable
    Path(script_name).chmod(0o755)

    print(f"Created wget download script: {script_name}")
    print(f"Run with: ./{script_name}")
    return script_name


def create_slurm_wget_script(wget_script, job_name="ia_wget_download"):
    """Create SLURM job script for wget downloader."""

    slurm_content = f'''#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --time=24:00:00
#SBATCH --mem=4G
#SBATCH --cpus-per-task=1
#SBATCH --output=ia_wget_%j.out
#SBATCH --error=ia_wget_%j.err

echo "Starting Internet Archive wget download job"
echo "Job ID: $SLURM_JOB_ID"
echo "Started at: $(date)"

# Run the wget download script
./{wget_script}

exit_code=$?
echo "Job completed at $(date) with exit code: $exit_code"
exit $exit_code
'''

    slurm_file = "submit_ia_wget.sh"
    with open(slurm_file, 'w') as f:
        f.write(slurm_content)

    Path(slurm_file).chmod(0o755)

    print(f"Created SLURM script: {slurm_file}")
    print(f"Submit with: sbatch {slurm_file}")
    return slurm_file


def main():
    parser = argparse.ArgumentParser(
        description="Simple Internet Archive bulk downloader using wget"
    )
    parser.add_argument(
        "--query",
        default='subject:"India -- Gazetteers"',
        help="Internet Archive search query"
    )
    parser.add_argument(
        "--download-dir",
        default="./pdfs",
        help="Download directory"
    )
    parser.add_argument(
        "--urls-only",
        action="store_true",
        help="Only generate URL file, don't create scripts"
    )
    parser.add_argument(
        "--create-slurm",
        action="store_true",
        help="Create SLURM submission script"
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Run wget download immediately"
    )

    args = parser.parse_args()

    print("Internet Archive wget-based downloader")
    print("=" * 50)
    print(f"Query: {args.query}")
    print(f"Download directory: {args.download_dir}")
    print()

    try:
        # Fetch identifiers
        print("Fetching identifiers from Internet Archive...")
        identifiers = fetch_all_identifiers(args.query)

        if not identifiers:
            print("No items found!")
            return

        # Generate URLs
        url_file = generate_pdf_urls(identifiers)

        if args.urls_only:
            print(f"URL file created: {url_file}")
            return

        # Create wget script
        wget_script = create_wget_script(url_file, args.download_dir)

        if args.create_slurm:
            create_slurm_wget_script(wget_script)

        if args.run_now:
            print(f"Running wget download now...")
            result = subprocess.run([f"./{wget_script}"], shell=True)
            sys.exit(result.returncode)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()