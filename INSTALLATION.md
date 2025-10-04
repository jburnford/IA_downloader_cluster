# Installation Guide

## Setup on Cluster

### 1. Clone Repository to Your Project Directory

```bash
# Navigate to your projects directory
cd /home/jic823/projects/def-jic823/

# Clone the repository
git clone git@github.com:jburnford/IA_downloader_cluster.git InternetArchive

# Navigate into the directory
cd InternetArchive
```

**Result:** You now have the code at:
```
/home/jic823/projects/def-jic823/InternetArchive/
```

### 2. Install Python Dependencies

```bash
# Make sure you're in the project directory
cd /home/jic823/projects/def-jic823/InternetArchive

# Install dependencies
pip install --user -r requirements.txt

# Or if using a virtual environment:
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Dependencies installed:**
- `requests` - For HTTP requests to Internet Archive API
- `tabulate` - For formatted table output in workflow manager

### 3. Configure for Your Environment

```bash
# Copy the example configuration
cp config.env.example config.env

# Edit configuration with your paths
nano config.env
```

**Update these settings in `config.env`:**

```bash
# Your PDF storage directory
PDF_DIR="/home/jic823/projects/def-jic823/pdf"

# Project directory (where you cloned the repo)
PROJECT_DIR="/home/jic823/projects/def-jic823/InternetArchive"

# Email for SLURM notifications
SLURM_EMAIL="your-email@institution.edu"

# SLURM job settings (adjust as needed)
SLURM_TIME="48:00:00"
SLURM_MEM="16G"
SLURM_CPUS="4"
```

### 4. Make Scripts Executable

```bash
# Make all shell scripts executable
chmod +x *.sh *.py
```

### 5. Set Up Database

The database will be created automatically when you first run a command with `--db-path`:

```bash
# Database will be created at this location
# /home/jic823/projects/def-jic823/InternetArchive/archive_tracking.db
```

### 6. Test Installation

```bash
# Test that scripts are accessible
./workflow_manager.py --help

# Test Python imports work
python3 -c "from archive_db import ArchiveDatabase; print('Success!')"

# Test downloader help
python3 archive_cluster_downloader.py --help
```

## Directory Structure After Installation

```
/home/jic823/projects/def-jic823/
├── InternetArchive/              # Cloned repository
│   ├── archive_cluster_downloader.py
│   ├── archive_db.py
│   ├── import_existing_pdfs.py
│   ├── ingest_ocr_results.py
│   ├── export_combined_data.py
│   ├── workflow_manager.py
│   ├── deduplicate_pdfs.py
│   ├── config.env              # Your configuration
│   ├── archive_tracking.db     # Created on first use
│   ├── *.sh                    # SLURM scripts
│   └── *.md                    # Documentation
│
├── pdf/                        # Your PDF collections
│   ├── results/                # olmOCR outputs
│   │   └── results/
│   │       ├── file1.jsonl
│   │       └── file2.jsonl
│   └── *.pdf
│
└── exports/                    # Generated exports (created later)
    ├── json/
    │   └── *.json
    └── markdown/
        └── *.md
```

## First Run Example

After installation, here's a complete example workflow:

### Option A: Download from Internet Archive

```bash
cd /home/jic823/projects/def-jic823/InternetArchive

# Download PDFs with tracking
python3 archive_cluster_downloader.py \
    --download-dir /home/jic823/projects/def-jic823/pdf \
    --subcollection "test_collection" \
    --db-path archive_tracking.db \
    --subject "India -- Gazetteers" \
    --max-items 5

# Check status
./workflow_manager.py status --db-path archive_tracking.db
```

### Option B: Import Existing PDFs

```bash
cd /home/jic823/projects/def-jic823/InternetArchive

# Import PDFs you already have
./import_existing_pdfs.py /home/jic823/projects/def-jic823/pdf \
    --db-path archive_tracking.db \
    --subcollection "my_pdfs" \
    --source "personal" \
    --dry-run  # Safe preview first

# If looks good, run for real
./import_existing_pdfs.py /home/jic823/projects/def-jic823/pdf \
    --db-path archive_tracking.db \
    --subcollection "my_pdfs" \
    --source "personal"
```

## Using with SLURM

### Update SLURM Script

Edit `run_archive_download.sh` to include database tracking:

```bash
nano run_archive_download.sh
```

Add to the python command:
```bash
python3 "$DOWNLOADER_SCRIPT" \
    --download-dir "$PDF_DIR" \
    --delay "$DOWNLOAD_DELAY" \
    --batch-size "$BATCH_SIZE" \
    --subject "$SUBJECT" \
    --start-year "$START_YEAR" \
    --end-year "$END_YEAR" \
    --sort "$SORT_ORDER" \
    --download-all-pdfs \
    --subcollection "gazetteers" \
    --db-path "$PROJECT_DIR/archive_tracking.db" \
    --verbose
```

### Submit Job

```bash
cd /home/jic823/projects/def-jic823/InternetArchive
sbatch run_archive_download.sh
```

## Troubleshooting Installation

### Python Module Not Found

```bash
# Check Python version
python3 --version  # Should be 3.8+

# Verify installation
pip list | grep -E 'requests|tabulate'

# If missing, reinstall
pip install --user -r requirements.txt
```

### Permission Denied on Scripts

```bash
# Make all scripts executable
chmod +x *.sh *.py

# Or individually:
chmod +x workflow_manager.py
chmod +x import_existing_pdfs.py
# etc.
```

### Database Creation Fails

```bash
# Check you have write permission in project directory
touch archive_tracking.db
rm archive_tracking.db

# Verify schema file exists
ls -lh database_schema.sql
```

### Git Clone Fails (SSH Key Issues)

If you get permission denied when cloning:

```bash
# Option 1: Use HTTPS instead
git clone https://github.com/jburnford/IA_downloader_cluster.git InternetArchive

# Option 2: Set up SSH key (one time)
ssh-keygen -t ed25519 -C "your-email@institution.edu"
cat ~/.ssh/id_ed25519.pub
# Add the output to GitHub → Settings → SSH Keys
```

## Updating the Code

When updates are pushed to GitHub:

```bash
cd /home/jic823/projects/def-jic823/InternetArchive

# Pull latest changes
git pull origin main

# Reinstall dependencies if requirements.txt changed
pip install --user -r requirements.txt
```

## Uninstallation

To remove everything:

```bash
# Backup database first if you want to keep it
cp /home/jic823/projects/def-jic823/InternetArchive/archive_tracking.db ~/backups/

# Remove the repository
rm -rf /home/jic823/projects/def-jic823/InternetArchive
```

## Next Steps

After installation:
1. Read **WORKFLOW_GUIDE.md** for complete workflow examples
2. Read **README.md** for feature details
3. Start with a small test (5-10 PDFs) to familiarize yourself
4. Check status regularly with `./workflow_manager.py status`

## Getting Help

- **Installation issues**: Check this file
- **Usage questions**: See WORKFLOW_GUIDE.md
- **Feature documentation**: See README.md
- **Overview**: See SUMMARY.md
