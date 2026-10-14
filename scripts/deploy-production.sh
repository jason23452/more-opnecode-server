#!/usr/bin/env bash
set -Eeuo pipefail

: "${OPENCODE_PASSWORD:?OPENCODE_PASSWORD must be configured in the production environment secrets}"
: "${OPENCODE_ADMIN_TOKEN:?OPENCODE_ADMIN_TOKEN must be configured in the production environment secrets}"
: "${DEPLOY_TAG:?DEPLOY_TAG must be set to the release tag}"

REPOSITORY="${DEPLOY_REPOSITORY:-/home/bojii/more-opencode-server}"
REMOTE_URL="${DEPLOY_REMOTE:-https://github.com/jason23452/more-opnecode-server.git}"

mkdir -p "${REPOSITORY}"
if ! git -C "${REPOSITORY}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git -C "${REPOSITORY}" init
fi

if git -C "${REPOSITORY}" remote get-url origin >/dev/null 2>&1; then
  git -C "${REPOSITORY}" remote set-url origin "${REMOTE_URL}"
else
  git -C "${REPOSITORY}" remote add origin "${REMOTE_URL}"
fi

git -C "${REPOSITORY}" fetch --no-tags origin "refs/tags/${DEPLOY_TAG}:refs/tags/${DEPLOY_TAG}"
git -C "${REPOSITORY}" checkout --force --detach "refs/tags/${DEPLOY_TAG}"
cd "${REPOSITORY}"
cp docker-compose.prod.yaml docker-compose.yaml
docker compose pull
docker compose up -d --remove-orphans
