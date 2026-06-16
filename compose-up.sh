#!/usr/bin/env bash
# Sobe o stack: se Ollama já roda em :11434, a API usa o da máquina; senão sobe container ollama.
set -e
cd "$(dirname "$0")"

BUILD=""
EXTRA=(-d)
while [[ $# -gt 0 ]]; do
  case "$1" in
    --build) BUILD="--build"; shift ;;
    *) EXTRA+=("$1"); shift ;;
  esac
done

host_ollama() {
  curl -sf --max-time 2 http://127.0.0.1:11434/ >/dev/null 2>&1
}

if host_ollama; then
  echo "Ollama em :11434 no host — API via host.docker.internal (sem container ollama)."
  docker compose up $BUILD "${EXTRA[@]}"
else
  echo "Ollama não no host — subindo upi_ollama."
  echo "  Depois: docker exec -it upi_ollama ollama pull llama3.2:3b"
  docker compose -f docker-compose.yml -f docker-compose.ollama.yml up $BUILD "${EXTRA[@]}"
fi
