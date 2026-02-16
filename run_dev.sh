#!/usr/bin/env bash
# ============================================================
# Quick launcher for development
# Usage:  bash run_dev.sh [extra args]
# Example: bash run_dev.sh --source videos/test.mp4 --model-size s
# ============================================================

set -euo pipefail

# Activate conda env (change name if needed)
CONDA_ENV="queue_estimation"

if command -v conda &> /dev/null; then
    echo "🔄  Activating conda environment: $CONDA_ENV"
    eval "$(conda shell.bash hook)"
    conda activate "$CONDA_ENV" 2>/dev/null || {
        echo "⚠️  Environment '$CONDA_ENV' not found. Using current Python."
    }
fi

echo "🚀  Starting Queue Wait-Time Estimation System …"
python -m src.main "$@"
