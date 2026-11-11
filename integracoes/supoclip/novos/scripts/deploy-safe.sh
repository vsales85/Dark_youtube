#!/usr/bin/env bash
# Rebuild and restart SupoClip without killing a video that is being generated.
#
#   scripts/deploy-safe.sh                  # backend + worker + frontend
#   scripts/deploy-safe.sh frontend         # only the listed services
#
# Builds first (slow), then waits until no "Vídeo do zero" job is queued or
# rendering and the worker queue is empty, and only then restarts (fast).
set -euo pipefail
cd "$(dirname "$0")/.."

services=("$@")
[ ${#services[@]} -eq 0 ] && services=(backend worker frontend)

echo "== Montando: ${services[*]}"
docker-compose build "${services[@]}"

busy() {
  MSYS_NO_PATHCONV=1 docker exec supoclip-redis sh -c '
    n=0
    for k in $(redis-cli --scan --pattern "studio:*"); do
      case $k in *user*|*pron*|*pick*|*profiles*) continue;; esac
      case "$(redis-cli get "$k")" in *\"rendering\"*|*\"queued\"*) n=$((n+1));; esac
    done
    q=$(redis-cli llen arq:queue:supoclip_tasks)
    echo $((n + q))'
}

# The frontend alone never touches running jobs.
needs_wait=0
for s in "${services[@]}"; do
  case "$s" in worker|backend) needs_wait=1;; esac
done

if [ "$needs_wait" -eq 1 ]; then
  while [ "$(busy)" != "0" ]; do
    echo "== Há vídeo sendo gerado; esperando terminar para reiniciar..."
    sleep 20
  done
fi

echo "== Reiniciando: ${services[*]}"
docker-compose up -d --no-deps "${services[@]}"
echo "== Pronto."
