#!/usr/bin/env python3
"""Utility script to clean problematic OCR rows from the tracking database."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Optional, Tuple


def positive_int(value: str) -> int:
    """Argparse helper to enforce positive integers."""

    try:
        ivalue = int(value)
    except ValueError as exc:  # pragma: no cover - argparse handles display
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if ivalue <= 0:
        raise argparse.ArgumentTypeError("Value must be positive")
    return ivalue


def remove_rows(
    conn: sqlite3.Connection,
    where_sql: str,
    params: Tuple,
    dry_run: bool,
    label: str,
) -> int:
    """Delete rows matching the provided WHERE clause."""

    cursor = conn.execute(
        f"SELECT COUNT(*) FROM ocr_processing WHERE {where_sql}", params
    )
    count = cursor.fetchone()[0]

    if count == 0:
        print(f"No rows matched criteria for {label}.")
        return 0

    print(f"Rows matching {label}: {count}")
    if dry_run:
        print("Dry-run mode: no changes made.")
        return count

    conn.execute(f"DELETE FROM ocr_processing WHERE {where_sql}", params)
    print(f"Deleted {count} row(s) for {label}.")
    return count


def build_where(
    threshold: Optional[int],
    subcollection: Optional[str],
    delete_all: bool,
) -> Tuple[str, Tuple]:
    """Construct the WHERE clause for the requested cleanup operation."""

    if delete_all:
        where_sql = "1=1"
        params: Tuple = ()
    elif threshold is not None:
        where_sql = "json_array_length(ocr_data) = 1 AND LENGTH(ocr_data) >= ?"
        params = (threshold,)
    elif subcollection:
        where_sql = (
            "pdf_file_id IN (SELECT id FROM pdf_files WHERE subcollection = ?)"
        )
        params = (subcollection,)
    else:
        raise ValueError(
            "No cleanup criteria provided. Use --threshold, --subcollection, or --all."
        )

    if subcollection and not delete_all and threshold is not None:
        where_sql += " AND pdf_file_id IN (SELECT id FROM pdf_files WHERE subcollection = ?)"
        params = params + (subcollection,)

    return where_sql, params


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove incorrect or oversized OCR rows from archive_tracking db"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("archive_tracking.db"),
        help="Path to the SQLite database (default: archive_tracking.db)",
    )
    parser.add_argument(
        "--threshold",
        type=positive_int,
        help="Delete rows where LENGTH(ocr_data) >= threshold and chunk count is 1",
    )
    parser.add_argument(
        "--subcollection",
        help="Restrict deletion to a specific subcollection",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Delete all rows from ocr_processing",
    )
    parser.add_argument(
        "--vacuum",
        action="store_true",
        help="Run VACUUM after deletions (skipped in dry-run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without deleting rows",
    )

    args = parser.parse_args()

    if not args.db_path.exists():
        parser.error(f"Database not found: {args.db_path}")

    try:
        where_sql, params = build_where(args.threshold, args.subcollection, args.all)
    except ValueError as exc:
        parser.error(str(exc))

    conn = sqlite3.connect(args.db_path)
    try:
        conn.row_factory = sqlite3.Row
        removed = remove_rows(conn, where_sql, params, args.dry_run, "cleanup")

        if not args.dry_run and removed > 0:
            conn.commit()
            if args.vacuum:
                print("Running VACUUM ...")
                conn.execute("VACUUM")
                print("VACUUM complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
