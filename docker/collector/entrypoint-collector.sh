#!/bin/sh
set -e

echo "Running collector task: $COLLECT_TASK"
python -m collector.tasks "$@"
