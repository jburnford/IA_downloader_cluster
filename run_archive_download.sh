#!/bin/bash
#SBATCH --job-name=archive_download

# Load configuration if available
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${CONFIG_FILE:-$SCRIPT_DIR/config.env}"

if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

# Set defaults from config or use hardcoded defaults
#SBATCH --time=${SLURM_TIME:-48:00:00}
#SBATCH --mem=${SLURM_MEM:-16G}
#SBATCH --cpus-per-task=${SLURM_CPUS:-4}
#SBATCH --output=${PDF_DIR:-/home/jic823/projects/def-jic823/pdf}/archive_download_%j.out
#SBATCH --error=${PDF_DIR:-/home/jic823/projects/def-jic823/pdf}/archive_download_%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=${SLURM_EMAIL:-jic823@uwo.ca}

# Set up environment
export PYTHONUNBUFFERED=1

# Apply config values
PROJECT_DIR="${PROJECT_DIR:-/home/jic823/projects/def-jic823/InternetArchive}"
PDF_DIR="${PDF_DIR:-/home/jic823/projects/def-jic823/pdf}"
DOWNLOADER_SCRIPT="${DOWNLOADER_SCRIPT:-$PROJECT_DIR/archive_cluster_downloader.py}"
DOWNLOAD_DELAY="${DOWNLOAD_DELAY:-0.05}"
BATCH_SIZE="${BATCH_SIZE:-200}"
SUBJECT="${SUBJECT:-India -- Gazetteers}"
START_YEAR="${START_YEAR:-1815}"
END_YEAR="${END_YEAR:-1960}"
SORT_ORDER="${SORT_ORDER:-date desc}"

# Navigate to the PDF directory
cd "$PDF_DIR" || {
    echo "Failed to change directory to $PDF_DIR"
    exit 1
}

# Load python module if needed (uncomment and adjust for your cluster)
# module load python/3.9

echo "Starting Archive.org download job at $(date)"
echo "Target directory: $PDF_DIR"
echo "Job ID: $SLURM_JOB_ID"
echo "Query: subject=\"$SUBJECT\", years=$START_YEAR-$END_YEAR, sort=$SORT_ORDER"

# Run the download script with optimized settings
python3 "$DOWNLOADER_SCRIPT" \
    --download-dir "$PDF_DIR" \
    --delay "$DOWNLOAD_DELAY" \
    --batch-size "$BATCH_SIZE" \
    --subject "$SUBJECT" \
    --start-year "$START_YEAR" \
    --end-year "$END_YEAR" \
    --sort "$SORT_ORDER" \
    --download-all-pdfs \
    --verbose

exit_code=$?

echo "Job completed at $(date) with exit code: $exit_code"

# If job failed or was interrupted, log it
if [ $exit_code -ne 0 ]; then
    echo "Job failed or was interrupted. Check logs and restart as needed."
fi

exit $exit_code
