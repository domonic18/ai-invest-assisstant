#!/bin/sh
set -e

if [ -n "$COLLECT_TASK" ] && [ "$COLLECT_TASK" != "default" ]; then
    echo "Running one-shot collector task: $COLLECT_TASK"
    python -m collector.tasks "$COLLECT_TASK" "$@"
    exit $?
fi

echo "Starting collector worker (queue + scheduler)"
python -m collector.worker
