#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if docker compose version >/dev/null 2>&1; then
  exec docker compose "$@"
elif [ -x .local/bin/docker-compose ]; then
  exec .local/bin/docker-compose "$@"
else
  echo 'Install Docker Compose v2 before continuing.' >&2
  exit 1
fi
