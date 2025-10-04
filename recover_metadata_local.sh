#!/bin/bash
# Run metadata recovery locally on the database
# This is faster than running on the cluster since we have better internet access

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DB_PATH="$SCRIPT_DIR/archive_tracking.db"

echo "========================================="
echo "Local Metadata Recovery"
echo "========================================="
echo ""
echo "This will recover metadata by querying:"
echo "  - Internet Archive API"
echo "  - Canadiana API"
echo "  - British Library (local metadata generation)"
echo "  - Saskatchewan Archives (filename parsing)"
echo ""
echo "Database: $DB_PATH"
echo ""

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    echo "ERROR: Database not found at $DB_PATH"
    echo "Please download it from NIBI first:"
    echo "  scp jic823@l2.nibi.usask.ca:/home/jic823/projects/def-jic823/InternetArchive/archive_tracking.db ."
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Check if recover_metadata.py exists
if [ ! -f "recover_metadata.py" ]; then
    echo "ERROR: recover_metadata.py not found"
    exit 1
fi

echo "Starting metadata recovery..."
echo ""

# This runs on the database directly without needing the actual PDF files
# It queries the pdf_files table and updates the items table

# For now, we'll use a Python script to process directly from the database
python3 << 'EOF'
import sqlite3
import sys
from pathlib import Path
from recover_metadata import MetadataRecovery

db_path = "archive_tracking.db"
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

print(f"Processing {len(pdf_files)} PDFs from database...")
print("")

for file_id, filename, filepath, subcollection in pdf_files:
    # Skip test collection
    if subcollection == "jacob":
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
    recovery.process_pdf(pdf_path, source_hint)

recovery.print_stats()
EOF

echo ""
echo "========================================="
echo "Metadata Recovery Complete!"
echo "========================================="
echo ""
echo "Upload the updated database back to NIBI:"
echo "  scp archive_tracking.db jic823@l2.nibi.usask.ca:/home/jic823/projects/def-jic823/InternetArchive/"
echo ""
