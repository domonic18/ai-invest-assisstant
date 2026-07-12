#!/bin/bash
set -e

# Run a collector task locally via uv.
# Usage: bash scripts/run-collector.sh kline [--period daily]

cd backend
uv run python -m collector.tasks "$@"
