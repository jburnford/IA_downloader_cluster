#!/bin/bash
# Setup script for creating virtual environment on cluster
# Run this ONCE from a login node (with internet access) before submitting jobs

set -e  # Exit on error

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==========================================="
echo "Internet Archive Downloader - Setup Script"
echo "==========================================="
echo ""
echo "This script will:"
echo "  1. Load required Python module"
echo "  2. Create a virtual environment"
echo "  3. Install Python dependencies"
echo ""
echo "Run this from a LOGIN NODE (not a compute node)"
echo ""

# Load configuration if available
CONFIG_FILE="${CONFIG_FILE:-$SCRIPT_DIR/config.env}"
if [ -f "$CONFIG_FILE" ]; then
    echo "Loading configuration from: $CONFIG_FILE"
    source "$CONFIG_FILE"
    echo ""
fi

# Set project directory
PROJECT_DIR="${PROJECT_DIR:-$SCRIPT_DIR}"
VENV_DIR="$PROJECT_DIR/venv"

echo "Project directory: $PROJECT_DIR"
echo "Virtual environment: $VENV_DIR"
echo ""

# Check if we're on a login node (has internet access)
echo "Testing internet connectivity..."
if ! ping -c 1 -W 2 archive.org &> /dev/null; then
    echo "WARNING: Cannot reach archive.org"
    echo "You may not have internet access. Are you on a login node?"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Load Python module (adjust for your cluster)
echo "Loading Python module..."
echo "If this fails, you need to find the correct module name for your cluster."
echo "Common options: python/3.9, python/3.10, python/3.11, StdEnv/2023, etc."
echo ""

# Try to load a Python module - customize this for your cluster!
# Uncomment and modify the appropriate line for your cluster:

# For Cedar/Graham/Beluga (Digital Research Alliance of Canada):
# module load StdEnv/2023 python/3.11

# For other clusters, try:
# module load python/3.9
# module load python/3.10
# module load python/3.11

# Check if user wants to specify module manually
if [ -z "${PYTHON_MODULE}" ]; then
    echo "No PYTHON_MODULE specified in config.env"
    echo "Please enter the Python module to load (or press Enter to skip):"
    read -r PYTHON_MODULE
fi

if [ -n "${PYTHON_MODULE}" ]; then
    echo "Loading module: $PYTHON_MODULE"
    module load $PYTHON_MODULE || {
        echo "ERROR: Failed to load module '$PYTHON_MODULE'"
        echo "Please check 'module avail python' to see available Python modules"
        exit 1
    }
else
    echo "Skipping module load - using system Python"
fi

echo ""

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 || echo "Python not found")
echo "Found: $PYTHON_VERSION"

if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found in PATH"
    echo "Please load the appropriate Python module first"
    exit 1
fi

echo ""

# Check if virtual environment already exists
if [ -d "$VENV_DIR" ]; then
    echo "Virtual environment already exists at: $VENV_DIR"
    read -p "Remove and recreate? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Removing existing virtual environment..."
        rm -rf "$VENV_DIR"
    else
        echo "Keeping existing virtual environment"
        echo "To reinstall dependencies, activate the venv and run:"
        echo "  source $VENV_DIR/bin/activate"
        echo "  pip install --upgrade -r requirements.txt"
        exit 0
    fi
fi

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv "$VENV_DIR" || {
    echo "ERROR: Failed to create virtual environment"
    echo "You may need to install python3-venv package or use virtualenv module"
    exit 1
}

echo "Virtual environment created successfully!"
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

echo ""

# Install dependencies
echo "Installing Python dependencies from requirements.txt..."
pip install -r "$PROJECT_DIR/requirements.txt" || {
    echo "ERROR: Failed to install dependencies"
    echo "Check that you have internet access"
    exit 1
}

echo ""
echo "==========================================="
echo "Setup Complete!"
echo "==========================================="
echo ""
echo "Virtual environment created at: $VENV_DIR"
echo ""
echo "Next steps:"
echo "  1. Review and edit config.env with your paths"
echo "  2. Submit a SLURM job with: sbatch run_archive_download.sh"
echo "  3. Monitor progress with: ./check_progress.sh"
echo ""
echo "Installed packages:"
pip list | grep -E 'requests|tabulate'
echo ""
echo "To manually activate this environment (for testing):"
echo "  source $VENV_DIR/bin/activate"
echo ""
