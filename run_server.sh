#!/bin/bash
# run.sh — start the FastAPI upload server

# Exit immediately if a command fails
set -e

# Navigate to script directory (project root)
cd "$(dirname "$0")"

# Activate virtual environment
source .venv/bin/activate

# Run Uvicorn on all interfaces, port 8000
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
