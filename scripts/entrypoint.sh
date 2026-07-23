#!/bin/sh
set -eu

is_true() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

if is_true "${MIGRATE_ON_START:-1}"; then
  attempt=1
  max_attempts="${MIGRATION_MAX_ATTEMPTS:-12}"
  until python manage.py migrate --noinput; do
    if [ "$attempt" -ge "$max_attempts" ]; then
      echo "Database migrations failed after ${attempt} attempts." >&2
      exit 1
    fi
    echo "Database is not ready for migrations (attempt ${attempt}/${max_attempts}); retrying..." >&2
    attempt=$((attempt + 1))
    sleep 3
  done
fi

PYTHONPATH=. python scripts/bootstrap_admin.py

exec "$@"
