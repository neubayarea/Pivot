#!/usr/bin/env bash
# One-step update on the VM: pull the latest code, rebuild and restart. Usage: deploy/oracle/deploy.sh [branch]
set -euo pipefail

cd "$(dirname "$0")"
branch="${1:-main}"

if [[ ! -f .env ]]; then
  echo "deploy/oracle/.env is missing: cp .env.example .env and fill it in first" >&2
  exit 1
fi

git fetch origin "$branch"
git checkout "$branch"
git pull --ff-only origin "$branch"
echo "deploying $(git log -1 --format='%h %s')"

docker compose up -d --build
docker image prune -f >/dev/null

# Wait for the app's healthcheck, then show where it is.
for _ in $(seq 30); do
  if docker compose exec -T app python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')" 2>/dev/null; then
    domain="$(grep -E '^PIVOT_DOMAIN=' .env | cut -d= -f2-)"
    echo "up: https://${domain}"
    exit 0
  fi
  sleep 2
done
echo "app did not become healthy; check: docker compose logs app" >&2
exit 1
