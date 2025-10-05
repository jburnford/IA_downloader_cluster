#!/usr/bin/env python3
"""Report OCR coverage statistics from the archive tracking database."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show counts of OCR records with and without stored data"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("archive_tracking.db"),
        help="Path to the SQLite database (default: archive_tracking.db)",
    )
    parser.add_argument(
        "--per-subcollection",
        action="store_true",
        help="Include per-subcollection summary",
    )

    args = parser.parse_args()

    if not args.db_path.exists():
        parser.error(f"Database not found: {args.db_path}")

    conn = sqlite3.connect(args.db_path)
    conn.row_factory = sqlite3.Row

    try:
        total = conn.execute("SELECT COUNT(*) AS count FROM ocr_processing").fetchone()[
            "count"
        ]
        with_data = conn.execute(
            "SELECT COUNT(*) AS count FROM ocr_processing WHERE ocr_data IS NOT NULL"
        ).fetchone()["count"]
        pending = total - with_data

        print("OCR Coverage Summary")
        print("====================")
        print(f"Total OCR rows       : {total}")
        print(f"Rows with ocr_data   : {with_data}")
        print(f"Rows missing ocr_data: {pending}")

        if args.per_subcollection:
            print("\nBy subcollection (rows with data / total):")
            query = conn.execute(
                """
                SELECT p.subcollection AS name,
                       COUNT(*) AS total_rows,
                       SUM(CASE WHEN o.ocr_data IS NOT NULL THEN 1 ELSE 0 END) AS with_data
                FROM ocr_processing o
                JOIN pdf_files p ON p.id = o.pdf_file_id
                GROUP BY p.subcollection
                ORDER BY p.subcollection
                """
            )
            for row in query:
                name = row["name"] or "(none)"
                print(
                    f"  {name}: {row['with_data']}/{row['total_rows']}"
                )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
