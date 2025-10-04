#!/usr/bin/env python3
"""
Test that database updates work correctly with a small sample.
"""

import sqlite3
from pathlib import Path
from recover_metadata import MetadataRecovery

db_path = "archive_tracking.db"

print("Testing Database Update")
print("=" * 70)

# Test files
test_filenames = [
    "acataloguelibra00brangoog.pdf",  # Internet Archive
    "10047.pdf",  # Canadiana
    "PioneerQuestionnaires_No.1-DietQuestionnaires_Box12934.pdf",  # Pioneer
]

# Create recovery instance
recovery = MetadataRecovery(db_path=db_path, delay=0.5, dry_run=False)

for filename in test_filenames:
    print(f"\nProcessing: {filename}")
    pdf_path = Path(filename)

    # Process and update database
    result = recovery.process_pdf(pdf_path, source_hint=None)

    if result:
        print(f"  ✓ Successfully processed")
    else:
        print(f"  ✗ Failed to process")

print("\n" + "=" * 70)
print("Checking database...")
print("=" * 70)

# Check what was written to database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

for filename in test_filenames:
    # Try to find the item by looking for the filename in different identifier formats
    name = Path(filename).stem

    cursor.execute("""
        SELECT identifier, title, year, creator, collection, LENGTH(metadata_json) as meta_len
        FROM items
        WHERE identifier LIKE ?
        LIMIT 1
    """, (f"%{name}%",))

    row = cursor.fetchone()
    if row:
        print(f"\n{filename}:")
        print(f"  Identifier: {row[0]}")
        print(f"  Title: {row[1] or 'N/A'}")
        print(f"  Year: {row[2] or 'N/A'}")
        print(f"  Creator: {row[3] or 'N/A'}")
        print(f"  Collection: {row[4] or 'N/A'}")
        print(f"  Metadata size: {row[5]} bytes")
    else:
        print(f"\n{filename}: NOT FOUND IN DATABASE")

conn.close()

print("\n" + "=" * 70)
print("Test complete!")
print("=" * 70)
