#!/usr/bin/env bash
# Build (if needed) and run the FinAlly container. Idempotent: safe to re-run.
#
# Usage: scripts/start_mac.sh [--build]
#   --build   force a rebuild of the image even if it already exists.
set -euo pipefail

IMAGE_NAME="finally"
CONTAINER_NAME="finally"
PORT="8000"
VOLUME_NAME="finally-data"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

FORCE_BUILD="false"
if [[ "${1:-}" == "--build" ]]; then
  FORCE_BUILD="true"
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: Docker is not installed. Install Docker Desktop from https://docker.com/products/docker-desktop and try again." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Error: Docker is installed but not running. Start Docker Desktop and try again." >&2
  exit 1
fi

if [[ "${FORCE_BUILD}" == "true" ]] || ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
  echo "Building ${IMAGE_NAME} image..."
  docker build -t "${IMAGE_NAME}" .
else
  echo "Image ${IMAGE_NAME} already exists (use --build to force a rebuild)."
fi

if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  echo "Removing existing ${CONTAINER_NAME} container..."
  docker rm -f "${CONTAINER_NAME}" >/dev/null
fi

ENV_FILE_ARGS=()
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
  ENV_FILE_ARGS=(--env-file "${PROJECT_ROOT}/.env")
else
  echo "Note: no .env file found. The app will run with the built-in market simulator."
  echo "      Chat needs LLM_MOCK=true or an OPENROUTER_API_KEY — copy .env.example to .env to set these."
fi

echo "Starting ${CONTAINER_NAME} container..."
docker run -d \
  --name "${CONTAINER_NAME}" \
  -p "${PORT}:8000" \
  -v "${VOLUME_NAME}:/app/db" \
  "${ENV_FILE_ARGS[@]}" \
  "${IMAGE_NAME}" >/dev/null

echo "Waiting for FinAlly to become healthy..."
TIMEOUT=60
ELAPSED=0
until curl -fsS "http://localhost:${PORT}/api/health" >/dev/null 2>&1; do
  if [[ "${ELAPSED}" -ge "${TIMEOUT}" ]]; then
    echo "Error: FinAlly did not become healthy within ${TIMEOUT}s. Check logs with: docker logs ${CONTAINER_NAME}" >&2
    exit 1
  fi
  sleep 1
  ELAPSED=$((ELAPSED + 1))
done

URL="http://localhost:${PORT}"
echo "FinAlly is running at ${URL}"

if command -v open >/dev/null 2>&1; then
  open "${URL}" || true
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "${URL}" || true
fi
