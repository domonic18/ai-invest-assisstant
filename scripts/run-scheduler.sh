#!/bin/bash
set -e

# Run local collector scheduler via uv.
# Usage: bash scripts/run-scheduler.sh

cd backend
uv run python -m collector.scheduler
