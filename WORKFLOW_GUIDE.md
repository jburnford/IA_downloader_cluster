# Internet Archive PDF Processing Workflow Guide

Complete guide for tracking PDFs through download → OCR → export pipeline.

## Overview

The workflow tracks PDFs through three stages:
1. **Download** - Get PDFs from Internet Archive with metadata
2. **OCR** - Process PDFs with olmOCR
3. **Export** - Combine metadata + OCR → JSON + Markdown files

All tracking happens in a SQLite database (`archive_tracking.db`) in the project directory.

## Initial Setup

```bash
cd /home/jic823/projects/def-jic823/InternetArchive
pip install -r requirements.txt
```

## Workflow Commands

### 1. Import Existing PDFs (Non-Internet Archive Sources)

If you have PDFs from other sources (personal uploads, other archives, scans):

```bash
# Import PDFs from a directory
./import_existing_pdfs.py /path/to/pdfs \
    --db-path archive_tracking.db \
    --subcollection "personal_scans" \
    --source "scan"

# Dry run first to see what will be imported
./import_existing_pdfs.py /path/to/pdfs \
    --subcollection "personal_scans" \
    --source "scan" \
    --dry-run

# Import recursively with title prefix
./import_existing_pdfs.py /path/to/pdfs \
    --subcollection "historical_docs" \
    --source "digitization" \
    --title-prefix "Historical Archive" \
    --recursive
```

**Metadata handling:**
- Title: Uses original filename (without .pdf extension)
- Identifier: Generated as `<source>_<filename_stem>`
- Exports (JSON/MD) use same base filename as original PDF

**Note:** Filenames are preserved as-is. The system doesn't try to parse them since naming conventions vary too much. You can add metadata manually to the database later if needed.

### 2. Download PDFs with Database Tracking (Internet Archive)

```bash
# Download with database tracking enabled
python3 archive_cluster_downloader.py \
    --download-dir /home/jic823/projects/def-jic823/pdf \
    --subject "India -- Gazetteers" \
    --start-year 1815 \
    --end-year 1960 \
    --subcollection "gazetteers" \
    --db-path /home/jic823/projects/def-jic823/InternetArchive/archive_tracking.db \
    --max-items 100

# Or submit as SLURM job (update run_archive_download.sh to include --db-path and --subcollection)
sbatch run_archive_download.sh
```

**What happens:**
- PDFs are downloaded to specified directory
- Metadata is saved to `items` table
- Each PDF file is recorded in `pdf_files` table with checksum
- Subcollection name helps organize different batches

### 3. Run olmOCR Processing

```bash
# Run olmOCR on your PDFs (your existing process)
# Output should go to: <pdf_directory>/results/results/<filename>.jsonl
```

### 4. Ingest OCR Results into Database

```bash
# Scan for OCR results and update database
./ingest_ocr_results.py /home/jic823/projects/def-jic823/pdf \
    --db-path /home/jic823/projects/def-jic823/InternetArchive/archive_tracking.db \
    --subcollection "gazetteers"

# Dry run first to see what would happen
./ingest_ocr_results.py /home/jic823/projects/def-jic823/pdf \
    --db-path /home/jic823/projects/def-jic823/InternetArchive/archive_tracking.db \
    --dry-run
```

**What happens:**
- Scans `<pdf_dir>/results/results/` for .jsonl files
- Matches JSONL files to PDFs in database
- Updates `ocr_processing` table with status='completed'
- Stores path to OCR JSON file

### 5. Export Combined Data

```bash
# Export to JSON + Markdown
./export_combined_data.py /home/jic823/projects/def-jic823/exports \
    --db-path /home/jic823/projects/def-jic823/InternetArchive/archive_tracking.db \
    --subcollection "gazetteers" \
    --type both

# Export only JSON
./export_combined_data.py /home/jic823/projects/def-jic823/exports \
    --type json

# Export only Markdown
./export_combined_data.py /home/jic823/projects/def-jic823/exports \
    --type markdown

# Dry run first
./export_combined_data.py /home/jic823/projects/def-jic823/exports \
    --dry-run
```

**What happens:**
- Creates `exports/json/` and `exports/markdown/` directories
- For each PDF with completed OCR:
  - Combines IA metadata + OCR text
  - Generates JSON file with all data
  - Generates Markdown file with YAML frontmatter
- Records exports in `exports` table

### 6. Check Workflow Status

```bash
# Overall statistics
./workflow_manager.py status --db-path archive_tracking.db

# Filter by subcollection
./workflow_manager.py status --subcollection "gazetteers"

# List PDFs that need OCR
./workflow_manager.py pending-ocr

# List items ready for export
./workflow_manager.py pending-exports

# See complete workflow status
./workflow_manager.py workflow

# Get details for specific item
./workflow_manager.py item indiagazetteer00hami
```

## Output Examples

### JSON Export Format

```json
{
  "identifier": "indiagazetteer00hami",
  "metadata": {
    "title": "India Gazetteer",
    "creator": "Hamilton, Walter",
    "year": 1828,
    "subject": "India -- Gazetteers",
    "item_url": "https://archive.org/details/indiagazetteer00hami"
  },
  "pdf": {
    "filename": "indiagazetteer00hami.pdf",
    "sha256": "abc123...",
    "size_bytes": 12345678
  },
  "ocr": {
    "engine": "olmOCR",
    "text": "Full OCR text here...",
    "statistics": {
      "record_count": 450,
      "total_length": 125000
    }
  }
}
```

### Markdown Export Format

```markdown
---
identifier: indiagazetteer00hami
title: "India Gazetteer"
creator: "Hamilton, Walter"
year: 1828
subjects:
  - "India -- Gazetteers"
source: https://archive.org/details/indiagazetteer00hami
pdf_filename: "indiagazetteer00hami.pdf"
ocr_engine: olmOCR
---

# India Gazetteer

## Description

Historical gazetteer of India...

## OCR Text

[Full OCR text here...]

---
*OCR processed 450 records, total length: 125000 characters*
```

## Database Schema

### Key Tables

- **items** - Internet Archive metadata
- **pdf_files** - Downloaded PDFs with checksums and paths
- **ocr_processing** - OCR status and JSON paths
- **exports** - Generated export files
- **audit_log** - Change tracking

### Useful Queries

```sql
-- Check overall progress
SELECT
    COUNT(*) as total_pdfs,
    SUM(CASE WHEN download_status='downloaded' THEN 1 ELSE 0 END) as downloaded,
    COUNT(o.id) as has_ocr,
    COUNT(e.id) as has_export
FROM pdf_files p
LEFT JOIN ocr_processing o ON p.id = o.pdf_file_id
LEFT JOIN exports e ON p.id = e.pdf_file_id;

-- Find files by subject
SELECT i.identifier, i.title, p.filename
FROM items i
JOIN pdf_files p ON i.identifier = p.identifier
WHERE i.subject LIKE '%Maps%';

-- Check OCR progress for subcollection
SELECT
    p.subcollection,
    COUNT(*) as total,
    SUM(CASE WHEN o.status='completed' THEN 1 ELSE 0 END) as completed
FROM pdf_files p
LEFT JOIN ocr_processing o ON p.id = o.pdf_file_id
GROUP BY p.subcollection;
```

## Tips & Best Practices

1. **Always use --subcollection** when downloading different batches - makes filtering easier

2. **Use dry-run first** for ingest and export scripts to preview changes

3. **Check status regularly**:
   ```bash
   ./workflow_manager.py status
   ```

4. **One PDF directory per subcollection** keeps OCR results organized:
   ```
   /home/jic823/projects/def-jic823/pdf_gazetteers/
   /home/jic823/projects/def-jic823/pdf_maps/
   /home/jic823/projects/def-jic823/pdf_newspapers/
   ```

5. **Database lives in project directory**, tracks all subcollections:
   ```
   /home/jic823/projects/def-jic823/InternetArchive/archive_tracking.db
   ```

6. **Backup database regularly**:
   ```bash
   cp archive_tracking.db archive_tracking.db.backup
   ```

## Troubleshooting

### OCR files not found

Check path structure:
```bash
ls -la /path/to/pdf_dir/results/results/*.jsonl
```

Should match pattern: `<pdf_name>.jsonl` for PDF `<pdf_name>.pdf`

### PDF not in database

Download didn't use `--db-path` flag. Re-run download or manually add:
```python
from archive_db import ArchiveDatabase
db = ArchiveDatabase("archive_tracking.db")
# ... add items manually
```

### Export has no OCR text

Check if `load_ocr_jsonl()` function in `export_combined_data.py` matches your JSONL structure. You may need to adjust text extraction logic based on actual olmOCR output format.

## Complete Example Workflow

```bash
# 1. Download PDFs
python3 archive_cluster_downloader.py \
    --download-dir /home/jic823/projects/def-jic823/pdf_gazetteers \
    --subcollection "gazetteers" \
    --db-path archive_tracking.db \
    --subject "India -- Gazetteers" \
    --max-items 50

# 2. Check status
./workflow_manager.py status --subcollection "gazetteers"

# 3. Run olmOCR (your process)
# ... OCR processing happens externally ...

# 4. Ingest OCR results
./ingest_ocr_results.py /home/jic823/projects/def-jic823/pdf_gazetteers \
    --db-path archive_tracking.db \
    --subcollection "gazetteers"

# 5. Check what's ready for export
./workflow_manager.py pending-exports --subcollection "gazetteers"

# 6. Generate exports
./export_combined_data.py exports_gazetteers \
    --db-path archive_tracking.db \
    --subcollection "gazetteers" \
    --type both

# 7. Verify exports created
ls -lh exports_gazetteers/json/
ls -lh exports_gazetteers/markdown/
```

## Next Steps

- Review exported files to ensure OCR text extraction is correct
- Adjust `load_ocr_jsonl()` in `export_combined_data.py` if needed
- Customize Markdown frontmatter fields as needed
- Add custom metadata fields to schema if required
