# Installation Guide

## Setup on Cluster

**IMPORTANT:** This setup is designed for HPC clusters with SLURM batch job systems. Compute nodes typically don't have internet access, so we create a virtual environment on the login node that's accessible from compute nodes.

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

### 2. Configure for Your Environment

**IMPORTANT:** Do this BEFORE running the setup script.

```bash
# Copy the example configuration
cp config.env.example config.env

# Edit configuration with your paths and cluster settings
nano config.env
```

**Required settings in `config.env`:**

```bash
# Your PDF storage directory
PDF_DIR="/home/jic823/projects/def-jic823/pdf"

# Project directory (where you cloned the repo)
PROJECT_DIR="/home/jic823/projects/def-jic823/InternetArchive"

# Python module to load (CRITICAL - adjust for your cluster!)
# For Digital Research Alliance clusters (Cedar/Graham/Beluga):
PYTHON_MODULE="StdEnv/2023 python/3.11"
# For other clusters, check: module avail python

# Email for SLURM notifications
SLURM_EMAIL="your-email@institution.edu"

# SLURM job settings (adjust as needed)
SLURM_TIME="48:00:00"
SLURM_MEM="16G"
SLURM_CPUS="4"
```

**Finding the right Python module:**
```bash
# List available Python modules on your cluster
module avail python

# Common options:
# - python/3.9
# - python/3.11
# - StdEnv/2023 python/3.11  (load multiple modules)
```

### 3. Run Setup Script (Login Node Only!)

**CRITICAL:** Run this on a **login node** with internet access, NOT a compute node.

```bash
# Make setup script executable
chmod +x setup_venv.sh

# Run the setup (this will install dependencies)
./setup_venv.sh
```

**What this does:**
1. Loads the Python module you specified
2. Creates a virtual environment at `$PROJECT_DIR/venv`
3. Installs dependencies from `requirements.txt`:
   - `requests` - For HTTP requests to Internet Archive API
   - `tabulate` - For formatted table output in workflow manager
4. The virtual environment is accessible from compute nodes

**If setup fails:**
- Check that `PYTHON_MODULE` in config.env is correct
- Verify you're on a login node with internet access
- Try: `ping archive.org` to confirm connectivity

```bash
# Activate the virtual environment
source venv/bin/activate

# Test that Python dependencies are available
python3 -c "import requests; import tabulate; print('Dependencies OK!')"

# Test database module
python3 -c "from archive_db import ArchiveDatabase; print('Database module OK!')"

# Test downloader help
python3 archive_cluster_downloader.py --help

# Deactivate when done testing
deactivate
```

**Expected output:**
```
Dependencies OK!
Database module OK!
[... downloader help text ...]
```

### 5. Make Scripts Executable

```bash
# Make all shell scripts executable
chmod +x *.sh *.py
```

### 6. Database Setup

The database will be created automatically when you first run a command with `--db-path`:

```bash
# Database will be created at this location when first used:
# /home/jic823/projects/def-jic823/InternetArchive/archive_tracking.db
```

## Directory Structure After Installation

```
/home/jic823/projects/def-jic823/
├── InternetArchive/              # Cloned repository
│   ├── venv/                     # Virtual environment (created by setup_venv.sh)
│   │   ├── bin/
│   │   ├── lib/
│   │   └── ...
│   ├── archive_cluster_downloader.py
│   ├── archive_db.py
│   ├── import_existing_pdfs.py
│   ├── ingest_ocr_results.py
│   ├── export_combined_data.py
│   ├── workflow_manager.py
│   ├── deduplicate_pdfs.py
│   ├── setup_venv.sh           # Setup script (run once)
│   ├── config.env              # Your configuration (copy from config.env.example)
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

### Option A: Submit SLURM Job (Recommended)

```bash
cd /home/jic823/projects/def-jic823/InternetArchive

# Submit the job to SLURM
sbatch run_archive_download.sh

# Monitor the job
squeue -u $USER

# Check progress
./check_progress.sh
```

### Option B: Test Locally First (Small Download)

**IMPORTANT:** Only do this on a login node for testing!

```bash
cd /home/jic823/projects/def-jic823/InternetArchive

# Activate virtual environment
source venv/bin/activate

# Download a few PDFs for testing
python3 archive_cluster_downloader.py \
    --download-dir /home/jic823/projects/def-jic823/pdf \
    --subcollection "test_collection" \
    --db-path archive_tracking.db \
    --subject "India -- Gazetteers" \
    --max-items 5

# Check status
./workflow_manager.py status --db-path archive_tracking.db

# Deactivate when done
deactivate
```

### Option C: Import Existing PDFs

```bash
cd /home/jic823/projects/def-jic823/InternetArchive

# Activate virtual environment
source venv/bin/activate

# Import PDFs you already have (dry run first)
./import_existing_pdfs.py /home/jic823/projects/def-jic823/pdf \
    --db-path archive_tracking.db \
    --subcollection "my_pdfs" \
    --source "personal" \
    --dry-run

# If looks good, run for real
./import_existing_pdfs.py /home/jic823/projects/def-jic823/pdf \
    --db-path archive_tracking.db \
    --subcollection "my_pdfs" \
    --source "personal"

# Deactivate when done
deactivate
```

## Customizing SLURM Jobs

The `run_archive_download.sh` script reads settings from `config.env`. To customize:

```bash
# Edit config.env to change search parameters
nano config.env
```

**Key settings to customize:**
```bash
# Search query settings
SUBJECT="India -- Gazetteers"
START_YEAR="1815"
END_YEAR="1960"
SORT_ORDER="date desc"

# Download settings
DOWNLOAD_DELAY="0.05"
BATCH_SIZE="200"

# SLURM resource allocation
SLURM_TIME="48:00:00"
SLURM_MEM="16G"
SLURM_CPUS="4"
```

Then submit the job:
```bash
sbatch run_archive_download.sh
```

## Troubleshooting Installation

### Virtual Environment Not Found (on compute node)

```bash
ERROR: Virtual environment not found at: /home/jic823/projects/def-jic823/InternetArchive/venv
Please run setup_venv.sh first from a login node
```

**Solution:** Run `./setup_venv.sh` from a login node.

### Module Load Fails

```bash
ERROR: Failed to load module 'python/3.11'
```

**Solution:** Find the correct module name for your cluster:
```bash
module avail python
# Update PYTHON_MODULE in config.env with the correct module name
```

### Dependencies Not Found (import requests fails)

```bash
# Activate venv and check if dependencies are installed
source venv/bin/activate
pip list | grep -E 'requests|tabulate'

# If missing, reinstall (from login node!)
pip install --upgrade -r requirements.txt
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

### Setup Script Can't Access Internet

```bash
WARNING: Cannot reach archive.org
You may not have internet access. Are you on a login node?
```

**Solution:** Make sure you're on a login node, not a compute node. Login nodes have internet access, compute nodes typically don't.

### Git Clone Fails (SSH Key Issues)

If you get permission denied when cloning:

```bash
# Option 1: Use HTTPS instead
git clone https://github.com/jburnford/IA_downloader_cluster.git InternetArchive

# Option 2: Set up SSH key (one time)
ssh-keygen -t ed25519 -C "jic823@usask.ca"
cat ~/.ssh/id_ed25519.pub
# Add the output to GitHub → Settings → SSH Keys
```

## Importing Existing PDFs and OCR Results

If you have existing PDFs and OCR results from olmOCR, follow these steps:

### Step 1: Import PDFs into Database

```bash
cd /home/jic823/projects/def-jic823/InternetArchive

# Activate virtual environment
source venv/bin/activate

# Import PDFs from a directory (dry run first to preview)
./import_existing_pdfs.py /path/to/pdf/directory \
    --db-path archive_tracking.db \
    --subcollection "collection_name" \
    --source "archive_org" \
    --dry-run

# Review the output, then run for real
./import_existing_pdfs.py /path/to/pdf/directory \
    --db-path archive_tracking.db \
    --subcollection "collection_name" \
    --source "archive_org"
```

**For multiple directories:**
```bash
# Import each directory separately with different subcollection names
./import_existing_pdfs.py /path/to/gazetteers \
    --db-path archive_tracking.db \
    --subcollection "gazetteers" \
    --source "archive_org"

./import_existing_pdfs.py /path/to/maps \
    --db-path archive_tracking.db \
    --subcollection "maps" \
    --source "archive_org"
```

### Step 2: Ingest OCR Results

```bash
# Ingest olmOCR results (expects results/results/*.jsonl structure)
./ingest_ocr_results.py /path/to/pdf/directory \
    --db-path archive_tracking.db

# Or specify the results directory directly
./ingest_ocr_results.py /path/to/pdf/directory \
    --results-dir /path/to/pdf/directory/results/results \
    --db-path archive_tracking.db
```

**For multiple directories:**
```bash
# Ingest results for each directory
./ingest_ocr_results.py /path/to/gazetteers --db-path archive_tracking.db
./ingest_ocr_results.py /path/to/maps --db-path archive_tracking.db
```

### Step 3: Verify Import

```bash
# Check workflow status
./workflow_manager.py status --db-path archive_tracking.db

# Export combined metadata + OCR data
./export_combined_data.py ./exports --db-path archive_tracking.db

# Deactivate when done
deactivate
```

### Example: Complete Workflow for Existing Data

```bash
# You have these directories:
# /home/jic823/projects/def-jic823/gazetteers/   (PDFs + results/)
# /home/jic823/projects/def-jic823/maps/         (PDFs + results/)
# /home/jic823/projects/def-jic823/newspapers/   (PDFs only, no OCR yet)

cd /home/jic823/projects/def-jic823/InternetArchive
source venv/bin/activate

# Import gazetteers (with OCR)
./import_existing_pdfs.py /home/jic823/projects/def-jic823/gazetteers \
    --db-path archive_tracking.db \
    --subcollection "gazetteers" \
    --source "archive_org"

./ingest_ocr_results.py /home/jic823/projects/def-jic823/gazetteers \
    --db-path archive_tracking.db

# Import maps (with OCR)
./import_existing_pdfs.py /home/jic823/projects/def-jic823/maps \
    --db-path archive_tracking.db \
    --subcollection "maps" \
    --source "archive_org"

./ingest_ocr_results.py /home/jic823/projects/def-jic823/maps \
    --db-path archive_tracking.db

# Import newspapers (no OCR yet)
./import_existing_pdfs.py /home/jic823/projects/def-jic823/newspapers \
    --db-path archive_tracking.db \
    --subcollection "newspapers" \
    --source "archive_org"

# Check status
./workflow_manager.py status --db-path archive_tracking.db

# Export everything
./export_combined_data.py /home/jic823/projects/def-jic823/exports \
    --db-path archive_tracking.db

deactivate
```

## Updating the Code

When updates are pushed to GitHub:

```bash
cd /home/jic823/projects/def-jic823/InternetArchive

# Pull latest changes
git pull origin main

# Reinstall dependencies if requirements.txt changed (from login node)
source venv/bin/activate
pip install --upgrade -r requirements.txt
deactivate
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
