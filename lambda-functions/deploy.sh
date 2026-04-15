#!/usr/bin/env bash
# Deploy SAM stack with DB/Twitch parameters from repo-root .env (same vars as CI).
# Plain `sam deploy` fails: template parameters have no Defaults and must be supplied.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SAM_ENV_FILE:-$SCRIPT_DIR/../.env}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

require() {
  local v="$1"
  if [[ -z "${!v:-}" ]]; then
    echo "deploy.sh: missing $v (set in $ENV_FILE or export in the shell)." >&2
    exit 1
  fi
}

require DB_HOST
require DB_NAME
require DB_USER
require DB_PASSWORD
require TWITCH_LIVE_CHECK_CLIENT_ID
require TWITCH_LIVE_CHECK_SECRET

OVERRIDES=(
  "DBHost=${DB_HOST}"
  "DBName=${DB_NAME}"
  "DBUser=${DB_USER}"
  "DBPassword=${DB_PASSWORD}"
  "DBPort=${DB_PORT:-5432}"
  "TwitchLiveCheckClientId=${TWITCH_LIVE_CHECK_CLIENT_ID}"
  "TwitchLiveCheckSecret=${TWITCH_LIVE_CHECK_SECRET}"
)
[[ -n "${ALERT_EMAIL:-}" ]] && OVERRIDES+=("AlertEmail=${ALERT_EMAIL}")
[[ -n "${CURRENT_SEASON:-}" ]] && OVERRIDES+=("CurrentSeason=${CURRENT_SEASON}")

cd "$SCRIPT_DIR"
exec sam deploy --parameter-overrides "${OVERRIDES[@]}"
