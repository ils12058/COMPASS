#!/usr/bin/env bash
# Explicit destructive reset only. Never dump, restore, issue credentials, or alter external resources.
set -euo pipefail
umask 077
: "${DEPLOY_SHA:?}" "${IMAGE:?}" "${APP_VERSION:?}" "${BUILD_TIME:?}"
[[ "$DEPLOY_SHA" =~ ^[0-9a-f]{40}$ ]]
[[ "$IMAGE" =~ ^registry.digitalocean.com/compass/compass-backend:$DEPLOY_SHA@sha256:[0-9a-f]{64}$ ]]
[[ "${ORG_CATALOG_ACTION:-check}" == check ]]
release=/opt/compass/releases/$DEPLOY_SHA
cd "$release"
export COMPASS_IMAGE="$IMAGE" COMPASS_SECRETS_DIR=/opt/compass/secrets
unset COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PROFILES STAGING_SEED_ENABLED STAGING_SEED_ONBOARDING_EMAIL STAGING_SEED_EMAIL_DOMAIN
compose=(docker compose --project-name compass -f "$release/compose.staging.yaml")
export DOCKER_CONFIG="$release/.registry"
exec 8>&1
exec 1>&2
phase=preflight
mode=${1:?}
recovery=()
[[ "$mode" == reset-preflight || "$mode" == reset ]]
# A reset retry can recognize its own durable fence; an ordinary preflight stays strict.
if [[ "$mode" == reset && -f /opt/compass/operator/resets/in-progress.json ]]; then
  recovery=(--recovery)
fi
apps=(proxy web worker beat realtime)
cleanup() {
  result=$?
  trap - EXIT
  if [[ "$result" != 0 && "$phase" != preflight ]]; then
    echo 'Reset failed after the destructive fence. App services remain stopped; rerun reset with the same SHA, image and domain. No rollback.' >&2
    # Disable automatic restarts before stopping even a partly started candidate.
    python3 deploy/staging/reset_state.py fence || true
  fi
  rm -f .candidate-config.json .reset-preflight.locked.json
  rm -rf .registry
  exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
configuration() {
  python3 deploy/runtime-secrets/check-runtime-secrets.py --secrets-dir /opt/compass/secrets --env-file /opt/compass/.env --owner compass >&2
  "${compose[@]}" config --format json > .candidate-config.json
}
pull_candidate() {
  docker pull "$IMAGE" >&2
  python3 deploy/staging/reset_state.py image
  # Configuration probe creates one temporary container, but has no DB tags or seed opt-in.
  python3 deploy/staging/reset_state.py settings-check
}
configuration
if [[ "$mode" == reset-preflight ]]; then
  python3 deploy/staging/reset_preflight.py .candidate-config.json > .reset-preflight.json
  pull_candidate
  cat .reset-preflight.json >&8
  exit
fi
IFS= read -r STAGING_SEED_ONBOARDING_EMAIL
export STAGING_SEED_ONBOARDING_EMAIL
exec 9>/opt/compass/.live-reset.lock
flock -n 9
# The unlocked snapshot is supplied by the runner. Check everything again while locked.
python3 deploy/staging/reset_preflight.py .candidate-config.json --locked "${recovery[@]}" > .reset-preflight.locked.json
cmp -s .reset-preflight.json .reset-preflight.locked.json || { echo 'Reset destination changed since unlocked preflight; refused' >&2; exit 1; }
pull_candidate
# Persistent checkpoint starts precisely at the destructive boundary, and admits only same-SHA recovery.
python3 deploy/staging/reset_state.py checkpoint
phase=fenced
python3 deploy/staging/reset_state.py fence
"${compose[@]}" rm -f "${apps[@]}"
# On a retry only: repair missing/stopped storage on pinned resources before running the same reset SQL.
# No app starts, no old data is restored, and configuration/image checks have already passed.
python3 deploy/staging/reset_state.py recover-storage
python3 deploy/staging/reset_state.py empty-database
python3 deploy/staging/reset_state.py empty-redis
"${compose[@]}" up -d --no-deps --force-recreate --pull never postgres redis
python3 deploy/staging/reset_state.py wait-storage
"${compose[@]}" run --rm --no-deps --pull never -T web python manage.py migrate --noinput </dev/null
for command in sync_identity_policy sync_canonical_services sync_institutional_forms; do
  "${compose[@]}" run --rm --no-deps --pull never -T web python manage.py "$command" </dev/null
done
"${compose[@]}" run --rm --no-deps --pull never -T web python manage.py initialize_organization_catalog --seed --reference "reset:$DEPLOY_SHA" </dev/null
"${compose[@]}" run --rm --no-deps --pull never -T web python manage.py initialize_organization_catalog --check </dev/null
"${compose[@]}" run --rm --no-deps --pull never -T web python manage.py migrate --check </dev/null
"${compose[@]}" run --rm --no-deps --pull never -T web python manage.py check --deploy --database default </dev/null
# Only these two one-offs receive the seed opt-in/domain and optional in-memory onboarding setting.
python3 deploy/staging/reset_state.py seed
python3 deploy/staging/reset_state.py verify
unset STAGING_SEED_ONBOARDING_EMAIL
"${compose[@]}" up -d --no-deps --pull never --wait --wait-timeout 180 web worker beat realtime proxy
"${compose[@]}" exec -T web python manage.py compass_doctor --worker-smoke --worker-timeout 10
source deploy/staging/deploy_common.sh
verify_running_release
publish_selector
python3 deploy/staging/host_preflight.py .candidate-config.json > .reset-after.json
python3 deploy/staging/reset_state.py receipt >&8
phase=complete
