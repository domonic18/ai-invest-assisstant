#!/bin/sh
set -e

if [ -n "$COLLECT_TASK" ] && [ "$COLLECT_TASK" != "default" ]; then
    echo "Running one-shot collector task: $COLLECT_TASK"
    python -m collector.runtime.cli "$COLLECT_TASK" "$@"
    exit $?
fi

MODE="${COLLECTOR_MODE:-worker}"

case "$MODE" in
  beat)
    echo "Starting Celery beat scheduler"
    exec python -m celery -A collector.celery_app beat \
      --scheduler collector.celery_beat:CollectorDatabaseScheduler \
      -s /tmp/celerybeat-schedule \
      --loglevel="${CELERY_LOG_LEVEL:-info}"
    ;;
  worker)
    QUEUE="${COLLECTOR_QUEUE:-collector.batch}"
    POOL="${COLLECTOR_POOL:-prefork}"
    MAX_TASKS="${COLLECTOR_MAX_TASKS_PER_CHILD:-200}"
    CONCURRENCY_OPT=""
    if [ -n "$COLLECTOR_CONCURRENCY" ]; then
      CONCURRENCY_OPT="--concurrency=$COLLECTOR_CONCURRENCY"
    fi
    echo "Starting Celery worker for queue: $QUEUE"
    exec python -m celery -A collector.celery_app worker \
      -Q "$QUEUE" \
      -n "${QUEUE##collector.}@%h" \
      -P "$POOL" \
      $CONCURRENCY_OPT \
      --prefetch-multiplier=1 \
      --max-tasks-per-child="$MAX_TASKS" \
      --loglevel="${CELERY_LOG_LEVEL:-info}"
    ;;
  *)
    echo "Unknown COLLECTOR_MODE: $MODE" >&2
    exit 1
    ;;
esac
