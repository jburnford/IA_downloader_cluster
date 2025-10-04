#!/usr/bin/env python3
"""
Ingest olmOCR results into the database.

Scans for OCR output JSONL files and updates the database with processing status.
Expected path structure: <pdf_directory>/results/results/<filename>.jsonl
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from archive_db import ArchiveDatabase


def find_ocr_results(pdf_directory: Path) -> dict:
    """
    Find all OCR result files in the expected directory structure.

    Returns:
        Dict mapping PDF filenames to their OCR JSON paths
    """
    results_dir = pdf_directory / "results" / "results"

    if not results_dir.exists():
        print(f"Warning: Results directory not found: {results_dir}")
        return {}

    ocr_results = {}
    for jsonl_file in results_dir.glob("*.jsonl"):
        # Match JSONL filename to PDF filename
        # Assumes: <pdfname>.pdf -> <pdfname>.jsonl
        pdf_filename = jsonl_file.stem + ".pdf"
        ocr_results[pdf_filename] = jsonl_file

    return ocr_results


def load_jsonl(filepath: Path) -> list:
    """Load JSONL file and return all records."""
    records = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return []


def ingest_ocr_results(
    db: ArchiveDatabase,
    pdf_directory: Path,
    subcollection: str = None,
    dry_run: bool = False
):
    """
    Ingest OCR results into database.

    Args:
        db: Database instance
        pdf_directory: Path to PDF directory
        subcollection: Filter by subcollection
        dry_run: If True, only show what would be done
    """
    print(f"Scanning for OCR results in: {pdf_directory}")
    print(f"Subcollection filter: {subcollection or 'All'}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print("-" * 70)

    # Find OCR result files
    ocr_results = find_ocr_results(pdf_directory)
    print(f"Found {len(ocr_results)} OCR result files")
    print()

    if not ocr_results:
        print("No OCR results found. Exiting.")
        return

    # Get PDFs from database that need OCR status updates
    all_pdfs = db.conn.execute("""
        SELECT p.id, p.identifier, p.filename, p.filepath, p.subcollection
        FROM pdf_files p
        WHERE p.download_status = 'downloaded' AND p.is_valid = 1
    """).fetchall()

    if subcollection:
        all_pdfs = [p for p in all_pdfs if p['subcollection'] == subcollection]

    print(f"Database has {len(all_pdfs)} eligible PDF files")
    print()

    updated_count = 0
    new_count = 0
    skipped_count = 0

    for pdf in all_pdfs:
        pdf_id = pdf['id']
        filename = pdf['filename']

        # Check if we have OCR results for this file
        if filename not in ocr_results:
            continue

        ocr_path = ocr_results[filename]

        # Check current OCR status
        existing = db.conn.execute("""
            SELECT id, status, json_output_path
            FROM ocr_processing
            WHERE pdf_file_id = ?
        """, (pdf_id,)).fetchone()

        # Load OCR data to validate
        ocr_data = load_jsonl(ocr_path)
        if not ocr_data:
            print(f"  Skipping {filename} - could not load OCR data")
            skipped_count += 1
            continue

        if existing:
            # Update existing record
            if existing['status'] == 'completed' and existing['json_output_path'] == str(ocr_path):
                skipped_count += 1
                continue  # Already up to date

            print(f"  Updating: {filename}")
            print(f"    Old status: {existing['status']}")
            print(f"    OCR file: {ocr_path.name}")

            if not dry_run:
                db.conn.execute("""
                    UPDATE ocr_processing
                    SET status = 'completed',
                        json_output_path = ?,
                        completed_date = ?
                    WHERE pdf_file_id = ?
                """, (str(ocr_path), datetime.now(), pdf_id))

            updated_count += 1
        else:
            # Create new OCR record
            print(f"  New OCR: {filename}")
            print(f"    OCR file: {ocr_path.name}")
            print(f"    Records: {len(ocr_data)}")

            if not dry_run:
                db.conn.execute("""
                    INSERT INTO ocr_processing (
                        pdf_file_id, status, json_output_path,
                        started_date, completed_date, ocr_engine
                    ) VALUES (?, 'completed', ?, ?, ?, 'olmOCR')
                """, (pdf_id, str(ocr_path), datetime.now(), datetime.now()))

            new_count += 1

    if not dry_run:
        db.conn.commit()

    print()
    print("=" * 70)
    print(f"Summary:")
    print(f"  New OCR records: {new_count}")
    print(f"  Updated records: {updated_count}")
    print(f"  Skipped (already current): {skipped_count}")

    if dry_run:
        print()
        print("This was a DRY RUN. No changes were made.")
        print("Run without --dry-run to apply changes.")


def main():
    parser = argparse.ArgumentParser(
        description="Ingest olmOCR results into tracking database"
    )
    parser.add_argument(
        "pdf_directory",
        type=Path,
        help="Path to PDF directory (e.g., /home/user/pdfs)"
    )
    parser.add_argument(
        "--db-path",
        default="archive_tracking.db",
        help="Path to SQLite database (default: archive_tracking.db)"
    )
    parser.add_argument(
        "--subcollection",
        help="Only process files from this subcollection"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )

    args = parser.parse_args()

    if not args.pdf_directory.exists():
        print(f"Error: PDF directory not found: {args.pdf_directory}")
        sys.exit(1)

    # Initialize database
    try:
        with ArchiveDatabase(args.db_path) as db:
            ingest_ocr_results(
                db=db,
                pdf_directory=args.pdf_directory,
                subcollection=args.subcollection,
                dry_run=args.dry_run
            )
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
