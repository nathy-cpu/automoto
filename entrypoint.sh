#!/bin/sh
set -eu

PORT="${PORT:-7860}"
WEB_CONCURRENCY="${WEB_CONCURRENCY:-1}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-true}"
RUN_COLLECTSTATIC="${RUN_COLLECTSTATIC:-true}"
RUN_SCHEDULER="${RUN_SCHEDULER:-false}"
SEED_ON_BOOT="${SEED_ON_BOOT:-false}"

if [ "$RUN_MIGRATIONS" = "true" ]; then
  python manage.py migrate --noinput
fi

if [ "$RUN_COLLECTSTATIC" = "true" ]; then
  python manage.py collectstatic --noinput
fi

if [ "$SEED_ON_BOOT" = "true" ]; then
  python manage.py seed_demo_data
fi

if [ "$RUN_SCHEDULER" = "true" ]; then
  python manage.py run_scheduler &
fi

exec gunicorn automoto.wsgi:application \
  --bind "0.0.0.0:${PORT}" \
  --workers "$WEB_CONCURRENCY" \
  --timeout 120
