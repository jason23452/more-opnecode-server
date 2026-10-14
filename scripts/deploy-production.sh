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

write_compose_env_value() {
  local value="$1"
  if [[ "${value}" == *$'\n'* || "${value}" == *$'\r'* ]]; then
    printf 'Compose secret values must not contain newlines\n' >&2
    return 1
  fi
  value="${value//\\/\\\\}"
  value="${value//\'/\\\'}"
  printf "'%s'" "${value}"
}

umask 077
env_file="${REPOSITORY}/.env"
temp_env_file="$(mktemp "${env_file}.XXXXXX")"
if [[ -f "${env_file}" ]]; then
  while IFS= read -r line || [[ -n "${line}" ]]; do
    if [[ "${line}" =~ ^[[:space:]]*(export[[:space:]]+)?(OPENCODE_PASSWORD|OPENCODE_ADMIN_TOKEN)[[:space:]]*= ]]; then
      continue
    fi
    printf '%s\n' "${line}" >>"${temp_env_file}"
  done <"${env_file}"
fi
password_env_value="$(write_compose_env_value "${OPENCODE_PASSWORD}")"
admin_token_env_value="$(write_compose_env_value "${OPENCODE_ADMIN_TOKEN}")"
printf 'OPENCODE_PASSWORD=%s\n' "${password_env_value}" >>"${temp_env_file}"
printf 'OPENCODE_ADMIN_TOKEN=%s\n' "${admin_token_env_value}" >>"${temp_env_file}"
chmod 600 "${temp_env_file}"
mv "${temp_env_file}" "${env_file}"

cp docker-compose.prod.yaml docker-compose.yaml
docker compose pull
docker compose up -d --remove-orphans
