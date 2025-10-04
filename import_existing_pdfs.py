#!/usr/bin/env python3
"""
Import existing PDFs into the database without Internet Archive metadata.

Useful for PDFs from other sources (personal uploads, other archives, etc.)
"""

import argparse
import hashlib
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from archive_db import ArchiveDatabase


def calculate_checksum(filepath: Path) -> str:
    """Calculate SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def validate_pdf(filepath: Path) -> bool:
    """Basic PDF validation."""
    try:
        with open(filepath, "rb") as f:
            header = f.read(5)
            return header == b"%PDF-"
    except Exception:
        return False


def extract_metadata_from_filename(filename: str) -> dict:
    """
    Extract minimal metadata from filename.

    Just uses the filename stem as the title.
    Filenames are too idiosyncratic to parse reliably.
    """
    stem = Path(filename).stem

    return {
        'title': stem,  # Keep original filename as title
        'original_filename': filename
    }


def generate_identifier(filename: str, source: str) -> str:
    """
    Generate a unique identifier for non-IA PDFs.

    Format: <source>_<filename_stem>
    Example: upload_myfile, scan_document123
    """
    stem = Path(filename).stem
    # Clean up stem - replace spaces and special chars
    clean_stem = stem.replace(' ', '_').replace('-', '_').lower()
    return f"{source}_{clean_stem}"


def import_pdfs(
    db: ArchiveDatabase,
    pdf_directory: Path,
    subcollection: str,
    source: str = "upload",
    title_prefix: str = None,
    recursive: bool = False,
    dry_run: bool = False
):
    """
    Import PDFs from a directory into the database.

    Args:
        db: Database instance
        pdf_directory: Directory containing PDFs
        subcollection: Subcollection name
        source: Source identifier (e.g., "upload", "scan", "personal")
        title_prefix: Optional prefix for titles
        recursive: Search subdirectories
        dry_run: If True, only show what would be done
    """
    print(f"Scanning directory: {pdf_directory}")
    print(f"Subcollection: {subcollection}")
    print(f"Source: {source}")
    print(f"Recursive: {recursive}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print("-" * 70)

    # Find PDF files
    if recursive:
        pdf_files = list(pdf_directory.rglob("*.pdf"))
    else:
        pdf_files = list(pdf_directory.glob("*.pdf"))

    print(f"Found {len(pdf_files)} PDF files")
    print()

    if not pdf_files:
        print("No PDF files found.")
        return

    imported_count = 0
    skipped_count = 0
    error_count = 0

    for pdf_path in sorted(pdf_files):
        filename = pdf_path.name

        # Check if already in database
        existing = db.get_pdf_file_by_path(str(pdf_path.absolute()))
        if existing:
            print(f"Skipping (already in database): {filename}")
            skipped_count += 1
            continue

        # Validate PDF
        if not validate_pdf(pdf_path):
            print(f"Error (invalid PDF): {filename}")
            error_count += 1
            continue

        # Generate identifier
        identifier = generate_identifier(filename, source)

        # Use filename stem as title (keep it simple)
        title = Path(filename).stem
        if title_prefix:
            title = f"{title_prefix}: {title}"

        print(f"Importing: {filename}")
        print(f"  Identifier: {identifier}")
        print(f"  Title: {title}")

        if dry_run:
            imported_count += 1
            continue

        try:
            # Calculate file info
            file_size = pdf_path.stat().st_size
            checksum = calculate_checksum(pdf_path)

            # Create minimal item record
            item_exists = db.get_item(identifier)
            if not item_exists:
                import json as json_module
                metadata_json = json_module.dumps({
                    "source": source,
                    "imported": True,
                    "original_filename": filename
                })

                db.conn.execute("""
                    INSERT INTO items (
                        identifier, title, download_date, metadata_json
                    ) VALUES (?, ?, ?, ?)
                """, (
                    identifier,
                    title,
                    datetime.now(),
                    metadata_json
                ))

            # Add PDF file record
            db.add_pdf_file(
                identifier=identifier,
                filename=filename,
                filepath=str(pdf_path.absolute()),
                subcollection=subcollection,
                size_bytes=file_size,
                sha256=checksum,
                download_status="downloaded",
                is_valid=True
            )

            db.conn.commit()
            imported_count += 1

        except Exception as e:
            print(f"  Error: {e}")
            error_count += 1

    print()
    print("=" * 70)
    print(f"Summary:")
    print(f"  Imported: {imported_count}")
    print(f"  Skipped (already in database): {skipped_count}")
    print(f"  Errors: {error_count}")

    if dry_run:
        print()
        print("This was a DRY RUN. No changes were made.")
        print("Run without --dry-run to import PDFs.")


def main():
    parser = argparse.ArgumentParser(
        description="Import existing PDFs into tracking database"
    )
    parser.add_argument(
        "pdf_directory",
        type=Path,
        help="Directory containing PDF files"
    )
    parser.add_argument(
        "--db-path",
        default="archive_tracking.db",
        help="Path to SQLite database (default: archive_tracking.db)"
    )
    parser.add_argument(
        "--subcollection",
        required=True,
        help="Subcollection name for organizing PDFs"
    )
    parser.add_argument(
        "--source",
        default="upload",
        help="Source identifier (default: upload). Examples: scan, personal, digitization"
    )
    parser.add_argument(
        "--title-prefix",
        help="Optional prefix to add to all titles (e.g., 'Personal Archive')"
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Search subdirectories recursively"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )

    args = parser.parse_args()

    if not args.pdf_directory.exists():
        print(f"Error: Directory not found: {args.pdf_directory}")
        sys.exit(1)

    if not args.pdf_directory.is_dir():
        print(f"Error: Not a directory: {args.pdf_directory}")
        sys.exit(1)

    # Initialize database
    try:
        with ArchiveDatabase(args.db_path) as db:
            import_pdfs(
                db=db,
                pdf_directory=args.pdf_directory,
                subcollection=args.subcollection,
                source=args.source,
                title_prefix=args.title_prefix,
                recursive=args.recursive,
                dry_run=args.dry_run
            )
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
