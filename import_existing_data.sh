#!/bin/bash
# Script to import existing PDFs and OCR results into the tracking database
# Run this AFTER running setup_venv.sh

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================="
echo "Import Existing PDFs and OCR Results"
echo "========================================="
echo ""

# Load configuration
if [ ! -f "config.env" ]; then
    echo "ERROR: config.env not found. Run 'cp config.env.example config.env' first"
    exit 1
fi

source config.env

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "ERROR: Virtual environment not found at: $VENV_DIR"
    echo "Please run ./setup_venv.sh first"
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

DB_PATH="$PROJECT_DIR/archive_tracking.db"

echo "Database will be created at: $DB_PATH"
echo ""
echo "Found the following directories with OCR results:"
echo "  1. /home/jic823/projects/def-jic823/pdf (main collection)"
echo "  2. /home/jic823/projects/def-jic823/pdf_india"
echo "  3. /home/jic823/projects/def-jic823/pdfs_jacob"
echo "  4. /home/jic823/projects/def-jic823/pdfs_jessylee/PioneerQuestionnairesPDFs"
echo ""
read -p "Do you want to import all of these? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled. You can import directories individually with:"
    echo "  source venv/bin/activate"
    echo "  ./import_existing_pdfs.py /path/to/pdfs --db-path archive_tracking.db --subcollection name"
    echo "  ./ingest_ocr_results.py /path/to/pdfs --db-path archive_tracking.db"
    exit 0
fi

echo ""
echo "========================================="
echo "Importing Collection 1: Main PDF Collection"
echo "========================================="
./import_existing_pdfs.py /home/jic823/projects/def-jic823/pdf \
    --db-path "$DB_PATH" \
    --subcollection "main" \
    --source "archive_org"

./ingest_ocr_results.py /home/jic823/projects/def-jic823/pdf \
    --db-path "$DB_PATH"

echo ""
echo "========================================="
echo "Importing Collection 2: India PDFs"
echo "========================================="
./import_existing_pdfs.py /home/jic823/projects/def-jic823/pdf_india \
    --db-path "$DB_PATH" \
    --subcollection "india" \
    --source "archive_org"

./ingest_ocr_results.py /home/jic823/projects/def-jic823/pdf_india \
    --db-path "$DB_PATH"

echo ""
echo "========================================="
echo "Importing Collection 3: Jacob's PDFs"
echo "========================================="
./import_existing_pdfs.py /home/jic823/projects/def-jic823/pdfs_jacob \
    --db-path "$DB_PATH" \
    --subcollection "jacob" \
    --source "archive_org"

./ingest_ocr_results.py /home/jic823/projects/def-jic823/pdfs_jacob \
    --db-path "$DB_PATH"

echo ""
echo "========================================="
echo "Importing Collection 4: JessyLee's Pioneer Questionnaires"
echo "========================================="
./import_existing_pdfs.py /home/jic823/projects/def-jic823/pdfs_jessylee/PioneerQuestionnairesPDFs \
    --db-path "$DB_PATH" \
    --subcollection "pioneer_questionnaires" \
    --source "archive_org"

./ingest_ocr_results.py /home/jic823/projects/def-jic823/pdfs_jessylee/PioneerQuestionnairesPDFs \
    --db-path "$DB_PATH"

echo ""
echo "========================================="
echo "Import Complete!"
echo "========================================="
echo ""
echo "Checking workflow status..."
./workflow_manager.py status --db-path "$DB_PATH"

echo ""
echo "To export all data:"
echo "  ./export_combined_data.py ./exports --db-path archive_tracking.db"
echo ""

deactivate
