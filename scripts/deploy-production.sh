#!/usr/bin/env bash
set -Eeuo pipefail

: "${OPENCODE_PASSWORD:?OPENCODE_PASSWORD must be configured in the production environment secrets}"
: "${OPENCODE_ADMIN_TOKEN:?OPENCODE_ADMIN_TOKEN must be configured in the production environment secrets}"
: "${DEPLOY_TAG:?DEPLOY_TAG must be set to the release tag}"

REPOSITORY="${DEPLOY_REPOSITORY:-/home/bojii/more-opencode-server}"

cd "${REPOSITORY}"
git fetch --no-tags origin "refs/tags/${DEPLOY_TAG}:refs/tags/${DEPLOY_TAG}"
git checkout --force --detach "refs/tags/${DEPLOY_TAG}"
cp docker-compose.yaml.prod docker-compose.yaml
docker compose build
docker compose up -d
