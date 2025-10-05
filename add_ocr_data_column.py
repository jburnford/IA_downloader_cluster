#!/usr/bin/env python3
"""
Add ocr_data column to ocr_processing table to store the actual OCR JSON content.
"""

import sqlite3
import sys
from pathlib import Path

def migrate_database(db_path: str):
    """Add ocr_data column to ocr_processing table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if column already exists
    cursor.execute("PRAGMA table_info(ocr_processing)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'ocr_data' in columns:
        print("Column 'ocr_data' already exists in ocr_processing table")
        conn.close()
        return

    print("Adding 'ocr_data' column to ocr_processing table...")

    # Add the column
    cursor.execute("""
        ALTER TABLE ocr_processing
        ADD COLUMN ocr_data TEXT
    """)

    conn.commit()
    conn.close()

    print("Migration complete!")
    print("You can now store OCR JSON data directly in the database.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 add_ocr_data_column.py <database_path>")
        sys.exit(1)

    db_path = sys.argv[1]
    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        sys.exit(1)

    migrate_database(db_path)
