#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/compose.local.yaml"
PRODUCTION_COMPOSE_FILE="${ROOT_DIR}/docker-compose.yaml.prod"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-production-images-verify}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:${FRONTEND_PORT:-3000}/}"
API_HEALTH_URL="${API_HEALTH_URL:-http://localhost:${BACKEND_PORT:-8000}/api/health}"

compose() {
  docker compose -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" "$@"
}

cleanup() {
  local status=$?
  trap - EXIT
  compose down --volumes --remove-orphans || true
  exit "${status}"
}
trap cleanup EXIT

OPENCODE_PASSWORD=local-compose-validation-only \
OPENCODE_ADMIN_TOKEN=local-compose-validation-only \
  docker compose -f "${PRODUCTION_COMPOSE_FILE}" config --quiet
compose config --quiet
compose build
compose up --detach

wait_for_http() {
  local url="$1"
  local label="$2"
  local attempts=30

  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if curl --fail --silent --show-error "${url}" >/dev/null; then
      printf '%s is responding: %s\n' "${label}" "${url}"
      return 0
    fi
    sleep 2
  done

  printf 'Timed out waiting for %s: %s\n' "${label}" "${url}" >&2
  compose logs
  return 1
}

wait_for_http "${FRONTEND_URL}" "Frontend"
wait_for_http "${API_HEALTH_URL}" "API health endpoint"
