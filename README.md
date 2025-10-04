# Internet Archive PDF Downloader

Bulk download tools for retrieving PDFs from the Internet Archive, optimized for HPC cluster environments (especially SLURM-based systems).

## Features

- **Flexible search queries** - Download by subject, collection, year range, or custom queries
- **Multiple download strategies** - Choose between Python requests-based or wget-based approaches
- **HPC cluster integration** - Built-in SLURM job submission and monitoring
- **Robust error handling** - Automatic retries, progress tracking, and graceful shutdown
- **Quality control** - PDF validation, checksum verification, and automatic deduplication
- **Concurrent downloads** - Multi-threaded downloading for improved performance
- **Resume capability** - Automatically resumes interrupted downloads
- **Configuration management** - Environment-based configuration for easy deployment

## Quick Start

### Installation

1. Clone the repository to your cluster:
```bash
cd /home/jic823/projects/def-jic823/
git clone <repository-url> InternetArchive
cd InternetArchive
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Configure for your environment:
```bash
cp config.env.example config.env
# Edit config.env with your paths and settings
nano config.env
```

### Basic Usage

#### Option 1: Python-based Downloader (Recommended)

**Local testing:**
```bash
python3 archive_cluster_downloader.py \
    --download-dir ./pdfs \
    --subject "India -- Gazetteers" \
    --start-year 1815 \
    --end-year 1960 \
    --max-items 10
```

**Submit SLURM job:**
```bash
sbatch run_archive_download.sh
```

**Monitor progress:**
```bash
./check_progress.sh
```

**Restart/resume download:**
```bash
./restart_download.sh
```

#### Option 2: wget-based Downloader

Best for simple bulk downloads without advanced filtering:

```bash
python3 ia_wget_downloader.py \
    --query 'subject:"India -- Gazetteers"' \
    --download-dir ./pdfs \
    --create-slurm

# Then submit the generated script
sbatch submit_ia_wget.sh
```

## Configuration

### config.env

The `config.env` file centralizes all configuration:

```bash
# Paths
PDF_DIR="/home/jic823/projects/def-jic823/pdf"
PROJECT_DIR="/home/jic823/projects/def-jic823/InternetArchive"

# SLURM settings
SLURM_EMAIL="your-email@institution.edu"
SLURM_TIME="48:00:00"
SLURM_MEM="16G"
SLURM_CPUS="4"

# Download settings
DOWNLOAD_DELAY="0.05"
BATCH_SIZE="200"

# Search parameters
SUBJECT="India -- Gazetteers"
START_YEAR="1815"
END_YEAR="1960"
SORT_ORDER="date desc"
```

## Command-Line Options

### archive_cluster_downloader.py

```bash
python3 archive_cluster_downloader.py [OPTIONS]

Options:
  --download-dir DIR          Download directory (default: ./pdfs)
  --start-from N             Start from item number N
  --max-items N              Maximum items to download
  --delay SECONDS            Delay between downloads (default: 0.1)
  --batch-size N             API batch size (default: 100)
  --subject TEXT             Subject filter (default: "India -- Gazetteers")
  --start-year YEAR          Earliest year (default: 1815)
  --end-year YEAR            Latest year (default: 1960)
  --sort ORDER               Sort order (default: "date desc")
  --query TEXT               Custom query (overrides other filters)
  --collection TEXT          Collection filter (can use multiple times)
  --download-all-pdfs        Download all PDF variants per item
  --create-slurm             Generate SLURM submission script
  --verbose                  Verbose logging
```

### Common Use Cases

**Download from specific collection:**
```bash
python3 archive_cluster_downloader.py \
    --collection "americana" \
    --subject "Maps" \
    --max-items 100
```

**Custom search query:**
```bash
python3 archive_cluster_downloader.py \
    --query 'creator:"Smith, John" AND year:[1900 TO 1950]'
```

**Resume from specific item:**
```bash
python3 archive_cluster_downloader.py \
    --start-from 500 \
    --download-dir ./pdfs
```

## Deduplication

Remove duplicate PDFs from previous downloads:

```bash
# Dry run (shows what would be deleted):
./deduplicate_pdfs.py /path/to/pdfs

# Actually remove duplicates:
./deduplicate_pdfs.py /path/to/pdfs --live

# With detailed report:
./deduplicate_pdfs.py /path/to/pdfs --live --report cleanup_report.json
```

The deduplication logic:
- Groups PDFs by Internet Archive identifier
- Prefers color over black-and-white versions
- Avoids `_text` versions (OCR only)
- Keeps larger file sizes when quality is similar
- Removes files within 10% size difference

## File Validation & Checksums

The downloader automatically:
- Validates PDF headers (`%PDF-` signature)
- Checks for EOF markers to detect truncation
- Calculates SHA256 checksums for all downloads
- Stores checksums in `file_checksums.json`
- Re-downloads invalid files

**Verify file integrity:**
```bash
# Checksums are stored in: <download_dir>/file_checksums.json
python3 -c "
import json
with open('pdfs/file_checksums.json') as f:
    checksums = json.load(f)
    print(f'Total files: {len(checksums)}')
    for name, info in list(checksums.items())[:5]:
        print(f'{name}: {info[\"sha256\"][:16]}... ({info[\"size\"]} bytes)')
"
```

## Progress Tracking

Progress is automatically saved to `download_progress.json`:

```json
{
  "downloaded": 1247,
  "failed": 23,
  "skipped": 89,
  "last_update": "2025-10-04T14:32:10.123456"
}
```

**Check progress:**
```bash
./check_progress.sh
```

Output shows:
- Current PDF count and disk usage
- Downloaded/failed/skipped statistics
- Success rate
- Estimated remaining items
- Running SLURM jobs
- Recent log entries

## Advanced Features

### Concurrent Downloads

When `--download-all-pdfs` is enabled and multiple PDFs exist for an item, they're downloaded concurrently using thread pools (default: 4 threads).

Configure in code:
```python
downloader = ClusterArchiveDownloader(
    concurrent_downloads=8,  # Increase for faster downloads
    ...
)
```

### Custom Queries

Build complex Archive.org queries:

```bash
# Multiple subjects (OR logic)
--query 'subject:(Maps OR Atlases) AND year:[1800 TO 1900]'

# Exclude items
--query 'subject:"India" NOT collection:fake-scans'

# Text search
--query 'title:"East India" AND creator:Hamilton'
```

See [Archive.org Advanced Search](https://archive.org/advancedsearch.php) for query syntax.

### SLURM Integration

**Monitor jobs:**
```bash
squeue -u $USER --name=archive_download
```

**View logs:**
```bash
tail -f /home/jic823/projects/def-jic823/pdf/archive_download_*.out
```

**Cancel job:**
```bash
scancel -u $USER --name=archive_download
```

## Troubleshooting

### Downloads are slow
- Decrease `--delay` (but respect Archive.org's rate limits)
- Increase `--batch-size` for API queries
- Enable concurrent downloads with `--download-all-pdfs`

### Many failed downloads
- Check network connectivity
- Verify Archive.org is accessible
- Increase retry count in code (`max_retries=5`)
- Check logs for specific error messages

### Duplicate PDFs
- Run `deduplicate_pdfs.py` to clean up
- Disable `--download-all-pdfs` flag to download only best quality
- The improved deduplication logic now skips similar-sized files automatically

### Invalid/corrupted PDFs
- Files are automatically validated after download
- Invalid files are re-downloaded on next run
- Check `file_checksums.json` for verification

### SLURM job fails immediately
- Check SBATCH directives in `run_archive_download.sh`
- Verify paths in `config.env`
- Check module availability (Python version)
- Review error logs in `*.err` files

## Project Structure

```
InternetArchive/
├── archive_cluster_downloader.py  # Main Python downloader
├── ia_wget_downloader.py          # Alternative wget-based downloader
├── deduplicate_pdfs.py            # Deduplication utility
├── run_archive_download.sh        # SLURM job submission script
├── restart_download.sh            # Restart/resume helper
├── check_progress.sh              # Progress monitoring script
├── config.env.example             # Configuration template
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## Best Practices

1. **Start small** - Test with `--max-items 10` before large downloads
2. **Use config.env** - Centralize configuration for easier management
3. **Monitor progress** - Run `check_progress.sh` periodically
4. **Validate downloads** - Checksums are calculated automatically
5. **Deduplicate regularly** - Run deduplication script after large batches
6. **Respect rate limits** - Use appropriate delays (0.05-0.1s recommended)
7. **Use version control** - Track your config.env changes

## Contributing

When making changes:
1. Test locally with small datasets first
2. Verify SLURM script generation
3. Check all scripts with ShellCheck
4. Update this README with new features

## License

[Your license here]

## Support

For issues or questions:
- Check the logs in your download directory
- Review Archive.org API documentation
- Submit issues to [repository issue tracker]

## Workflow Tracking & Metadata Management

This repository includes a complete workflow tracking system for managing PDFs through download → OCR → export pipeline.

### Quick Start with Database Tracking

```bash
# 1. Download PDFs with metadata tracking
python3 archive_cluster_downloader.py \
    --download-dir /path/to/pdfs \
    --subcollection "gazetteers" \
    --db-path archive_tracking.db \
    --subject "India -- Gazetteers"

# 2. After running olmOCR, ingest results
./ingest_ocr_results.py /path/to/pdfs --db-path archive_tracking.db

# 3. Export combined metadata + OCR to JSON and Markdown
./export_combined_data.py ./exports --db-path archive_tracking.db

# 4. Check workflow status
./workflow_manager.py status
```

See **[WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md)** for complete documentation.

### Additional Tools

- **`archive_db.py`** - SQLite database interface
- **`ingest_ocr_results.py`** - Import olmOCR results into database
- **`export_combined_data.py`** - Generate JSON + Markdown from metadata + OCR
- **`workflow_manager.py`** - CLI for checking status and managing workflow
- **`database_schema.sql`** - Complete database schema

## Acknowledgments

Built for downloading historical materials from the Internet Archive for academic research purposes.
