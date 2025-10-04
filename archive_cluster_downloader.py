#!/usr/bin/env python3
"""
Bulk download PDFs from Archive.org for cluster environments.

Optimized for NIBI cluster usage with SLURM job submission support.
Downloads PDFs tagged "India -- Gazetteers" from Archive.org by default.
"""

import argparse
import hashlib
import json
import logging
import os
import shlex
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests

# Import database module if available
try:
    from archive_db import ArchiveDatabase
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    print("Warning: archive_db module not found. Database tracking disabled.")


class ClusterArchiveDownloader:
    def __init__(
        self,
        download_dir="pdfs",
        max_retries=3,
        delay=0.1,
        concurrent_downloads=4,
        batch_size=100,
        subject="India -- Gazetteers",
        start_year=1815,
        end_year=1960,
        sort_order="date desc",
        search_query=None,
        collections=None,
        download_all_pdfs=False,
        subcollection=None,
        db_path=None,
    ):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.max_retries = max_retries
        self.delay = delay
        self.concurrent_downloads = concurrent_downloads
        self.batch_size = batch_size
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; ClusterResearchBot/1.0; Academic Use)"
            }
        )

        self.subject = subject
        self.start_year = start_year
        self.end_year = end_year
        self.sort_order = sort_order
        self.search_query = search_query
        self.collections = list(collections) if collections else []
        self.download_all_pdfs = download_all_pdfs
        self.subcollection = subcollection

        # Database tracking
        self.db = None
        if DB_AVAILABLE and db_path:
            try:
                self.db = ArchiveDatabase(db_path)
                self.logger.info(f"Database tracking enabled: {db_path}")
            except Exception as e:
                self.logger.warning(f"Could not initialize database: {e}")

        # Progress tracking
        self.progress_file = self.download_dir / "download_progress.json"
        self.checksum_file = self.download_dir / "file_checksums.json"
        self.downloaded_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self.checksums = self._load_checksums()

        # Signal handling for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        # Setup logging
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging for cluster environment."""
        log_file = self.download_dir / f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
        )
        self.logger = logging.getLogger(__name__)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}. Saving progress and shutting down...")
        self.save_progress()
        self._save_checksums()
        sys.exit(0)

    def _load_checksums(self):
        """Load previously calculated checksums."""
        if self.checksum_file.exists():
            try:
                with open(self.checksum_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Could not load checksum file: {e}")
        return {}

    def _save_checksums(self):
        """Save checksums to file."""
        try:
            with open(self.checksum_file, "w") as f:
                json.dump(self.checksums, f, indent=2)
        except Exception as e:
            self.logger.warning(f"Could not save checksums: {e}")

    def _calculate_checksum(self, filepath, algorithm="sha256"):
        """Calculate file checksum."""
        hash_func = hashlib.new(algorithm)
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hash_func.update(chunk)
            return hash_func.hexdigest()
        except Exception as e:
            self.logger.warning(f"Error calculating checksum for {filepath}: {e}")
            return None

    def save_progress(self):
        """Save current progress to file."""
        progress_data = {
            "downloaded": self.downloaded_count,
            "failed": self.failed_count,
            "skipped": self.skipped_count,
            "last_update": datetime.now().isoformat(),
        }

        with open(self.progress_file, "w") as f:
            json.dump(progress_data, f, indent=2)

    def load_progress(self):
        """Load previous progress if available."""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, "r") as f:
                    data = json.load(f)
                    self.downloaded_count = data.get("downloaded", 0)
                    self.failed_count = data.get("failed", 0)
                    self.skipped_count = data.get("skipped", 0)
                    self.logger.info(
                        f"Resumed from previous session: {self.downloaded_count} downloaded, "
                        f"{self.failed_count} failed, {self.skipped_count} skipped"
                    )
            except Exception as e:
                self.logger.warning(f"Could not load progress file: {e}")

    def build_search_query(self):
        """Build the search query for Archive.org API."""
        if self.search_query:
            return self.search_query

        clauses = []

        if self.collections:
            if len(self.collections) == 1:
                clauses.append(f"collection:{self.collections[0]}")
            else:
                collection_query = " OR ".join(self.collections)
                clauses.append(f"collection:({collection_query})")

        if self.subject:
            subject_escaped = self.subject.replace('"', '\\"')
            clauses.append(f'subject:"{subject_escaped}"')

        if self.start_year is not None or self.end_year is not None:
            start = self.start_year if self.start_year is not None else "*"
            end = self.end_year if self.end_year is not None else "*"
            clauses.append(f"year:[{start} TO {end}]")

        return " AND ".join(clauses) if clauses else "*:*"

    def get_search_results(self, start=0, rows=100):
        """Get search results from Archive.org API."""
        params = {
            "q": self.build_search_query(),
            "fl": "identifier,title,year,collection,format",
            "rows": rows,
            "start": start,
            "output": "json",
        }

        if self.sort_order:
            params["sort"] = self.sort_order

        url = "https://archive.org/advancedsearch.php"

        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                self.logger.warning(f"Search attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.delay * (2**attempt))
                else:
                    raise

    def get_item_metadata(self, identifier):
        """Get detailed metadata for an Archive.org item."""
        url = f"https://archive.org/metadata/{identifier}"

        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                self.logger.warning(f"Metadata attempt {attempt + 1} for {identifier} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.delay)
                else:
                    return None

    @staticmethod
    def _safe_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def get_pdf_candidates(self, metadata):
        """Return a list of PDF files sorted by quality heuristics, with deduplication."""
        files = metadata.get("files")
        if not files:
            return []

        pdf_candidates = []
        for file_info in files:
            name = file_info.get("name") or ""
            fmt = file_info.get("format") or ""
            if not name:
                continue
            if name.lower().endswith(".pdf") or "pdf" in fmt.lower():
                pdf_candidates.append(file_info)

        if not pdf_candidates:
            return []

        def sort_key(file_info):
            name_lower = (file_info.get("name") or "").lower()
            fmt_lower = (file_info.get("format") or "").lower()
            size_val = self._safe_int(file_info.get("size"))

            # Prioritize: color over bw, larger size, avoid _text suffix
            color_score = 0 if "_bw" in name_lower or "bw" in fmt_lower else 1
            text_penalty = -1 if "_text" in name_lower else 0

            return (color_score, text_penalty, size_val)

        pdf_candidates.sort(key=sort_key, reverse=True)

        # Deduplicate: remove files that are likely duplicates
        # Keep files that differ significantly in size (>10%) or have different base names
        if self.download_all_pdfs and len(pdf_candidates) > 1:
            deduplicated = [pdf_candidates[0]]  # Always keep the best quality
            best_size = self._safe_int(pdf_candidates[0].get("size"))

            for candidate in pdf_candidates[1:]:
                candidate_size = self._safe_int(candidate.get("size"))

                # Skip if size is within 10% of best file (likely duplicate/derivative)
                if best_size > 0:
                    size_diff_percent = abs(candidate_size - best_size) / best_size * 100
                    if size_diff_percent < 10:
                        self.logger.debug(
                            f"Skipping {candidate.get('name')} - similar size to best PDF "
                            f"({size_diff_percent:.1f}% difference)"
                        )
                        continue

                deduplicated.append(candidate)

            return deduplicated

        return pdf_candidates

    def validate_pdf(self, filepath):
        """Validate that the downloaded file is a valid PDF."""
        try:
            with open(filepath, "rb") as f:
                header = f.read(5)
                # PDF files must start with %PDF-
                if header != b"%PDF-":
                    return False

                # Check for EOF marker (simple check)
                f.seek(-1024, 2)  # Seek to last 1024 bytes
                tail = f.read()
                if b"%%EOF" not in tail:
                    self.logger.warning(f"PDF may be truncated: {filepath.name}")
                    return False

            return True
        except Exception as e:
            self.logger.warning(f"PDF validation error for {filepath.name}: {e}")
            return False

    def download_file(self, identifier, file_info):
        """Download a specific file."""
        filename = file_info.get("name")
        if not filename:
            self.logger.warning(f"Skipping file with missing name for {identifier}")
            self.skipped_count += 1
            return False

        download_url = f"https://archive.org/download/{identifier}/{filename}"
        local_path = self.download_dir / filename

        if local_path.exists():
            # Validate existing file
            if self.validate_pdf(local_path):
                self.logger.debug(f"Skipping {filename} - already exists and is valid")
                self.skipped_count += 1
                return True
            else:
                self.logger.warning(f"Existing file {filename} is invalid, re-downloading")
                try:
                    local_path.unlink()
                except OSError as e:
                    self.logger.error(f"Could not remove invalid file {filename}: {e}")
                    self.failed_count += 1
                    return False

        size_display = file_info.get("size", "unknown")
        self.logger.info(f"Downloading {filename} ({size_display} bytes)")

        for attempt in range(self.max_retries):
            try:
                response = self.session.get(download_url, stream=True, timeout=120)
                response.raise_for_status()

                with open(local_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=32768):
                        if chunk:
                            f.write(chunk)

                # Validate downloaded PDF
                if not self.validate_pdf(local_path):
                    self.logger.error(f"Downloaded file {filename} is not a valid PDF")
                    try:
                        local_path.unlink()
                    except OSError:
                        pass

                    if attempt < self.max_retries - 1:
                        time.sleep(self.delay * (2**attempt))
                        continue
                    else:
                        self.failed_count += 1
                        return False

                # Calculate and store checksum
                file_size = local_path.stat().st_size
                checksum = self._calculate_checksum(local_path)
                if checksum:
                    self.checksums[filename] = {
                        "sha256": checksum,
                        "size": file_size,
                        "downloaded": datetime.now().isoformat(),
                        "identifier": identifier,
                    }
                    # Save checksums periodically
                    if self.downloaded_count % 10 == 0:
                        self._save_checksums()

                # Save to database
                if self.db:
                    self.db.add_pdf_file(
                        identifier=identifier,
                        filename=filename,
                        filepath=str(local_path.absolute()),
                        subcollection=self.subcollection,
                        size_bytes=file_size,
                        sha256=checksum,
                        download_status="downloaded",
                        is_valid=True
                    )

                self.logger.info(f"Successfully downloaded {filename}")
                self.downloaded_count += 1
                return True

            except Exception as e:
                self.logger.warning(f"Download attempt {attempt + 1} for {filename} failed: {e}")
                if local_path.exists():
                    try:
                        local_path.unlink()
                    except OSError as unlink_error:
                        self.logger.debug(f"Could not remove partial file {filename}: {unlink_error}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.delay * (2**attempt))
                else:
                    self.logger.error(
                        f"Failed to download {filename} after {self.max_retries} attempts"
                    )
                    self.failed_count += 1
                    return False

    def download_batch(self, start_item=0, max_items=None):
        """Download all PDFs from the search results."""
        query = self.build_search_query()
        self.logger.info("Starting bulk download of Archive.org PDFs")
        self.logger.info(f"Download directory: {self.download_dir.absolute()}")
        self.logger.info(f"Search query: {query}")
        if self.sort_order:
            self.logger.info(f"Sort order: {self.sort_order}")
        self.logger.info(f"Starting from item: {start_item}")
        self.logger.info(f"Max items: {max_items or 'All'}")
        self.logger.info(
            f"Download all PDFs per item: {'Yes' if self.download_all_pdfs else 'No'}"
        )

        self.load_progress()

        start = start_item
        items_processed = 0

        while True:
            if max_items and items_processed >= max_items:
                self.logger.info(f"Reached maximum items limit: {max_items}")
                break

            try:
                results = self.get_search_results(start=start, rows=self.batch_size)
            except Exception as e:
                self.logger.error(f"Failed to get search results: {e}")
                break

            response = results.get("response", {}) if results else {}
            docs = response.get("docs", [])
            total_found = response.get("numFound", 0)

            if not docs:
                self.logger.info("No more documents to process")
                break

            self.logger.info(f"Processing batch {start}-{start + len(docs)} of {total_found}")

            for doc in docs:
                if max_items and items_processed >= max_items:
                    break

                identifier = doc.get("identifier")
                if not identifier:
                    self.logger.warning("Encountered result without identifier, skipping entry")
                    self.failed_count += 1
                    continue

                title = doc.get("title", "Unknown")[:100]
                self.logger.info(
                    f"Processing ({items_processed + 1}): {identifier} - {title}"
                )

                metadata = self.get_item_metadata(identifier)
                if not metadata:
                    self.logger.warning(f"Could not get metadata for {identifier}")
                    self.failed_count += 1
                    items_processed += 1
                    continue

                # Save item metadata to database
                if self.db:
                    self.db.add_item(identifier, metadata)

                pdf_candidates = self.get_pdf_candidates(metadata)
                if not pdf_candidates:
                    self.logger.warning(f"No PDF found for {identifier}")
                    self.failed_count += 1
                    items_processed += 1
                    continue

                files_to_download = (
                    pdf_candidates if self.download_all_pdfs else [pdf_candidates[0]]
                )
                if self.download_all_pdfs and len(files_to_download) > 1:
                    self.logger.info(
                        f"Found {len(files_to_download)} PDF files for {identifier}; downloading all matches"
                    )

                # Use concurrent downloads if enabled
                if self.concurrent_downloads > 1 and len(files_to_download) > 1:
                    with ThreadPoolExecutor(max_workers=self.concurrent_downloads) as executor:
                        futures = {
                            executor.submit(self.download_file, identifier, file_info): file_info
                            for file_info in files_to_download
                        }
                        for future in as_completed(futures):
                            try:
                                future.result()
                            except Exception as e:
                                file_info = futures[future]
                                self.logger.error(
                                    f"Error downloading {file_info.get('name')}: {e}"
                                )
                else:
                    for file_info in files_to_download:
                        self.download_file(identifier, file_info)

                items_processed += 1

                if items_processed % 10 == 0:
                    self.save_progress()

                time.sleep(self.delay)

            start += len(docs)

            if start >= total_found:
                break

        self.save_progress()
        self._save_checksums()
        self.logger.info(
            f"Download complete. Downloaded: {self.downloaded_count}, "
            f"Failed: {self.failed_count}, Skipped: {self.skipped_count}"
        )

        return self.downloaded_count, self.failed_count, self.skipped_count


def create_slurm_script(
    script_path,
    download_dir="./pdfs",
    max_items=None,
    job_name="archive_download",
    time_limit="24:00:00",
    memory="8G",
    cpus=2,
    delay=0.05,
    batch_size=200,
    extra_args=None,
):
    """Create a SLURM job submission script."""

    extra_args = extra_args or []
    script_path_quoted = shlex.quote(script_path)
    download_dir_quoted = shlex.quote(download_dir)

    cli_lines = [
        f"--download-dir {download_dir_quoted}",
        f"--delay {delay}",
        f"--batch-size {batch_size}",
    ]

    if max_items:
        cli_lines.append(f"--max-items {max_items}")

    cli_lines.extend(extra_args)
    cli_lines.append("--verbose")

    cli_block = " \\\n    ".join(cli_lines)

    slurm_script = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --time={time_limit}
#SBATCH --mem={memory}
#SBATCH --cpus-per-task={cpus}
#SBATCH --output=archive_download_%j.out
#SBATCH --error=archive_download_%j.err

# Load required modules (adjust for your cluster)
# module load python/3.9

# Set up environment
export PYTHONUNBUFFERED=1

# Create download directory
mkdir -p {download_dir_quoted}

# Run the download script
python3 {script_path_quoted} \\
    {cli_block}

echo "Job completed at $(date)"
"""

    slurm_file = Path("submit_archive_download.sh")
    with open(slurm_file, "w") as f:
        f.write(slurm_script)

    os.chmod(slurm_file, 0o755)

    print(f"Created SLURM script: {slurm_file}")
    print(f"Submit with: sbatch {slurm_file}")

    return slurm_file


def main():
    parser = argparse.ArgumentParser(
        description="Bulk download Archive.org PDFs for cluster environments"
    )
    parser.add_argument("--download-dir", default="./pdfs", help="Download directory")
    parser.add_argument("--start-from", type=int, default=0, help="Start from item number")
    parser.add_argument("--max-items", type=int, help="Maximum items to download")
    parser.add_argument("--delay", type=float, default=0.1, help="Delay between downloads")
    parser.add_argument("--batch-size", type=int, default=100, help="API batch size")
    parser.add_argument("--subject", default="India -- Gazetteers", help="Subject filter")
    parser.add_argument(
        "--start-year", type=int, default=1815, help="Earliest publication year to include"
    )
    parser.add_argument(
        "--end-year", type=int, default=1960, help="Latest publication year to include"
    )
    parser.add_argument(
        "--sort",
        default="date desc",
        help="Archive.org sort order (e.g., 'date desc', 'date asc', 'downloads desc')",
    )
    parser.add_argument(
        "--query",
        help="Override the generated advanced search query with a custom value",
    )
    parser.add_argument(
        "--collection",
        action="append",
        dest="collections",
        help="Archive.org collection filter (use multiple times)",
    )
    parser.add_argument(
        "--download-all-pdfs",
        action="store_true",
        help="Download every PDF file attached to each item",
    )
    parser.add_argument(
        "--subcollection",
        help="Subcollection name for organizing PDFs in database",
    )
    parser.add_argument(
        "--db-path",
        help="Path to SQLite database file (enables database tracking)",
    )
    parser.add_argument("--create-slurm", action="store_true", help="Create SLURM submission script")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.create_slurm:
        script_path = os.path.abspath(__file__)
        extra_cli_args = []

        if args.query:
            extra_cli_args.append(f"--query {shlex.quote(args.query)}")
        else:
            if args.subject:
                extra_cli_args.append(f"--subject {shlex.quote(args.subject)}")
            if args.start_year is not None:
                extra_cli_args.append(f"--start-year {args.start_year}")
            if args.end_year is not None:
                extra_cli_args.append(f"--end-year {args.end_year}")

        if args.sort:
            extra_cli_args.append(f"--sort {shlex.quote(args.sort)}")

        if args.collections:
            for collection in args.collections:
                extra_cli_args.append(f"--collection {shlex.quote(collection)}")

        if args.download_all_pdfs:
            extra_cli_args.append("--download-all-pdfs")

        create_slurm_script(
            script_path=script_path,
            download_dir=args.download_dir,
            max_items=args.max_items,
            delay=args.delay,
            batch_size=args.batch_size,
            extra_args=extra_cli_args,
        )
        return

    print("Archive.org Cluster PDF Downloader")
    print("=" * 50)
    print(f"Download directory: {args.download_dir}")
    print(f"Start from: {args.start_from}")
    print(f"Max items: {args.max_items or 'All'}")
    print(f"Delay: {args.delay}s")
    print(f"Batch size: {args.batch_size}")
    if args.query:
        print(f"Custom query override: {args.query}")
    else:
        print(f"Subject filter: {args.subject or 'None'}")
        collections_display = ", ".join(args.collections) if args.collections else "None"
        print(f"Collections: {collections_display}")
        start_display = args.start_year if args.start_year is not None else "*"
        end_display = args.end_year if args.end_year is not None else "*"
        print(f"Year range: {start_display} to {end_display}")
        print(f"Sort order: {args.sort or 'Archive default'}")
    print(f"Download all PDFs per item: {'Yes' if args.download_all_pdfs else 'No'}")
    print()

    downloader = ClusterArchiveDownloader(
        download_dir=args.download_dir,
        delay=args.delay,
        batch_size=args.batch_size,
        subject=args.subject,
        start_year=args.start_year,
        end_year=args.end_year,
        sort_order=args.sort,
        search_query=args.query,
        collections=args.collections,
        download_all_pdfs=args.download_all_pdfs,
        subcollection=args.subcollection,
        db_path=args.db_path,
    )

    try:
        downloaded, failed, skipped = downloader.download_batch(
            start_item=args.start_from, max_items=args.max_items
        )
        print(f"\nFinal results: {downloaded} downloaded, {failed} failed, {skipped} skipped")

        if failed > downloaded * 0.1:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nDownload interrupted by user.")
        downloader.save_progress()
        sys.exit(0)
    except Exception as e:
        print(f"\nDownload failed with error: {e}")
        downloader.save_progress()
        sys.exit(1)


if __name__ == "__main__":
    main()
