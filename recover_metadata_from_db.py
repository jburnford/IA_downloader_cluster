#!/usr/bin/env python3
"""
Recover metadata for PDFs by reading filenames from the database.
This version properly updates existing database items with fetched metadata.
"""

import sqlite3
import sys
from pathlib import Path
from recover_metadata import MetadataRecovery

def main():
    db_path = "archive_tracking.db"

    print("=" * 70)
    print("Database Metadata Recovery")
    print("=" * 70)
    print(f"\nDatabase: {db_path}")
    print()

    # Create recovery instance
    recovery = MetadataRecovery(db_path=db_path, delay=0.5, dry_run=False)

    # Get all PDF files from database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, filename, filepath, subcollection
        FROM pdf_files
        ORDER BY subcollection, filename
    """)

    pdf_files = cursor.fetchall()
    conn.close()

    print(f"Found {len(pdf_files)} PDFs in database")
    print()

    # Track progress
    processed = 0
    skipped = 0

    for file_id, filename, filepath, subcollection in pdf_files:
        processed += 1

        # Skip test collection
        if subcollection == "jacob":
            skipped += 1
            if processed % 100 == 0:
                print(f"Progress: {processed}/{len(pdf_files)} processed, {skipped} skipped (jacob collection)")
            continue

        # Create a Path object from filename
        pdf_path = Path(filename)

        # Determine source hint based on subcollection
        source_hint = None
        if subcollection == "pioneer_questionnaires":
            source_hint = "saskatchewan_archives"
        elif subcollection == "india":
            source_hint = None  # Auto-detect (IA or BL)
        elif subcollection == "main":
            source_hint = None  # Auto-detect (Canadiana or others)

        # Process the PDF
        try:
            recovery.process_pdf(pdf_path, source_hint)
        except Exception as e:
            print(f"ERROR processing {filename}: {e}")
            recovery.stats["errors"] += 1

        # Print progress every 50 files
        if processed % 50 == 0:
            print(f"\nProgress: {processed}/{len(pdf_files)} processed")
            print(f"  IA: {recovery.stats['internet_archive']}, "
                  f"Canadiana: {recovery.stats['canadiana']}, "
                  f"BL: {recovery.stats['british_library']}, "
                  f"Custom: {recovery.stats['custom']}, "
                  f"Not found: {recovery.stats['not_found']}")

    print()
    recovery.print_stats()

if __name__ == "__main__":
    main()
