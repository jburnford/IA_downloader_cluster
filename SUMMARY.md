# Internet Archive PDF Workflow - Complete System

## What We Built

A complete workflow tracking system for managing PDF collections from download through OCR to final export, with support for **multiple PDF sources** (Internet Archive + personal uploads/scans).

## Key Features

### 1. Multiple PDF Sources
- ✅ Internet Archive downloads with full metadata
- ✅ Import existing PDFs from any source
- ✅ Automatic metadata extraction from filenames
- ✅ All sources tracked in single database

### 2. Complete Workflow Tracking
- Downloads → OCR Processing → Exports
- Status tracking at each stage
- Progress monitoring
- Subcollection organization

### 3. Smart Deduplication
- Prevents duplicate downloads
- Removes similar-sized PDFs automatically
- Post-download cleanup tools

### 4. Data Integrity
- PDF validation (header + EOF check)
- SHA256 checksums for all files
- Audit logging

### 5. Rich Exports
- **JSON**: Complete structured data (metadata + OCR text)
- **Markdown**: Human-readable with YAML frontmatter
- Includes olmOCR statistics and version info

## File Structure

```
InternetArchive/
├── Core Downloads
│   ├── archive_cluster_downloader.py  # IA downloader with DB tracking
│   ├── ia_wget_downloader.py          # Alternative wget-based downloader
│   └── import_existing_pdfs.py        # Import non-IA PDFs
│
├── Database & Tracking
│   ├── database_schema.sql            # Complete schema
│   ├── archive_db.py                  # Database interface module
│   └── workflow_manager.py            # Status checking CLI
│
├── OCR Integration
│   ├── ingest_ocr_results.py          # Import olmOCR results
│   └── export_combined_data.py        # Generate JSON + Markdown
│
├── Utilities
│   ├── deduplicate_pdfs.py            # Remove duplicate files
│   ├── test_ocr_parsing.py            # Test OCR parsing
│   └── check_progress.sh              # Legacy progress checker
│
├── SLURM Job Scripts
│   ├── run_archive_download.sh        # Main job script
│   ├── restart_download.sh            # Resume downloads
│   └── config.env.example             # Configuration template
│
├── Documentation
│   ├── README.md                      # Main documentation
│   ├── WORKFLOW_GUIDE.md              # Complete workflow guide
│   └── SUMMARY.md                     # This file
│
└── Configuration
    ├── requirements.txt                # Python dependencies
    └── config.env                      # Your settings (create from .example)
```

## Quick Start Examples

### Example 1: Internet Archive Collection

```bash
# Download from IA with tracking
python3 archive_cluster_downloader.py \
    --download-dir /home/user/pdfs_gazetteers \
    --subcollection "gazetteers" \
    --db-path archive_tracking.db \
    --subject "India -- Gazetteers" \
    --start-year 1815 \
    --end-year 1960

# After olmOCR processing
./ingest_ocr_results.py /home/user/pdfs_gazetteers --db-path archive_tracking.db

# Export combined data
./export_combined_data.py exports --db-path archive_tracking.db --subcollection "gazetteers"
```

### Example 2: Personal PDF Collection

```bash
# Import existing PDFs
./import_existing_pdfs.py /home/user/my_scans \
    --db-path archive_tracking.db \
    --subcollection "personal_archive" \
    --source "scan" \
    --recursive

# After olmOCR processing
./ingest_ocr_results.py /home/user/my_scans --db-path archive_tracking.db

# Export
./export_combined_data.py exports --db-path archive_tracking.db --subcollection "personal_archive"
```

### Example 3: Mixed Sources

```bash
# 1. Download from IA
python3 archive_cluster_downloader.py \
    --download-dir /pdfs_ia \
    --subcollection "ia_gazetteers" \
    --db-path archive_tracking.db

# 2. Import personal PDFs
./import_existing_pdfs.py /pdfs_personal \
    --subcollection "personal_docs" \
    --db-path archive_tracking.db

# 3. Check overall status
./workflow_manager.py status --db-path archive_tracking.db

# Shows combined statistics from all sources!
```

## Database Structure

### Tables
- **items** - Metadata (from IA or filename extraction)
- **pdf_files** - File tracking with checksums
- **ocr_processing** - OCR status and results
- **exports** - Generated output files
- **audit_log** - Change history

### Views
- **workflow_status** - Complete status per item
- **pending_ocr** - Files needing OCR
- **pending_export** - Files ready for export

## Output Examples

### JSON Export
```json
{
  "identifier": "upload_hamilton_india_1828",
  "metadata": {
    "title": "Hamilton India Gazetteer",
    "creator": "Hamilton, Walter",
    "year": 1828
  },
  "pdf": {
    "filename": "Hamilton_India_Gazetteer_1828.pdf",
    "sha256": "abc123...",
    "size_bytes": 12345678
  },
  "ocr": {
    "engine": "olmOCR",
    "version": "0.3.4",
    "text": "Full OCR text here...",
    "statistics": {
      "page_count": 28,
      "total_length": 430982,
      "input_tokens": 46480,
      "output_tokens": 7514
    }
  }
}
```

### Markdown Export
```markdown
---
identifier: upload_hamilton_india_1828
title: "Hamilton India Gazetteer"
creator: "Hamilton, Walter"
year: 1828
pdf_filename: "Hamilton_India_Gazetteer_1828.pdf"
pdf_pages: 28
ocr_engine: olmOCR
ocr_version: "0.3.4"
---

# Hamilton India Gazetteer

## OCR Text

[Full text here...]

---

*OCR processed 28 pages in 15 records*
*Total length: 430,982 characters*
*olmOCR version: 0.3.4*
```

## Common Workflows

### Workflow 1: New IA Download
1. `archive_cluster_downloader.py` (with --db-path)
2. Run olmOCR externally
3. `ingest_ocr_results.py`
4. `export_combined_data.py`

### Workflow 2: Import Existing Collection
1. `import_existing_pdfs.py` (extracts metadata from filenames)
2. Run olmOCR externally
3. `ingest_ocr_results.py`
4. `export_combined_data.py`

### Workflow 3: Check Status Anytime
```bash
./workflow_manager.py status
./workflow_manager.py pending-ocr
./workflow_manager.py pending-exports
./workflow_manager.py item <identifier>
```

## Tips

1. **One database, multiple PDF directories** - Database lives in project dir, tracks everything
2. **Always use --subcollection** - Makes filtering and organizing easier
3. **Dry-run first** - Most scripts support `--dry-run` to preview changes
4. **Backup database** - `cp archive_tracking.db archive_tracking.db.backup`
5. **Filename conventions matter** - Include year and author in filenames for better metadata extraction

## Metadata Extraction from Filenames

The system automatically extracts:

| Filename | → | Extracted Metadata |
|----------|---|-------------------|
| `Hamilton_India_1828.pdf` | → | Title: "Hamilton India", Year: 1828 |
| `1902_Pioneer_Questionnaire.pdf` | → | Title: "Pioneer Questionnaire", Year: 1902 |
| `Smith-Travel-Diary-1856.pdf` | → | Title: "Smith Travel Diary", Year: 1856 |

## Performance Features

- **Concurrent downloads** - Multi-threaded when `--download-all-pdfs` enabled
- **Resume capability** - Progress tracking allows restart after interruption
- **Incremental processing** - Only processes new/changed files
- **Efficient queries** - Database indexes on common fields

## Next Steps

1. **Review WORKFLOW_GUIDE.md** for detailed command examples
2. **Copy config.env.example** to config.env and customize
3. **Run initial import** on your existing PDFs
4. **Check status** regularly with workflow_manager.py
5. **Customize metadata extraction** in import_existing_pdfs.py for your naming conventions

## Support

For issues or questions:
- Check logs in download directory
- Review database with: `sqlite3 archive_tracking.db`
- Test OCR parsing with: `python3 test_ocr_parsing.py`
- See README.md and WORKFLOW_GUIDE.md for detailed documentation
