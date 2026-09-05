#!/usr/bin/env bash
# Stop and remove the FinAlly container. The finally-data volume is left intact,
# so portfolio/watchlist/chat history persists across restarts. Safe to re-run.
set -euo pipefail

CONTAINER_NAME="finally"
VOLUME_NAME="finally-data"

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: Docker is not installed." >&2
  exit 1
fi

if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  echo "Stopping and removing ${CONTAINER_NAME} container..."
  docker rm -f "${CONTAINER_NAME}" >/dev/null
  echo "Container stopped."
else
  echo "No ${CONTAINER_NAME} container is running."
fi

echo "Data volume '${VOLUME_NAME}' left intact. To delete it permanently: docker volume rm ${VOLUME_NAME}"
