#!/usr/bin/env bash
# Coordinated application rollout. Never starts/recreates PostgreSQL or Redis; never rolls back SQL.
set -euo pipefail
umask 077
: "${DEPLOY_SHA:?}" "${IMAGE:?}" "${APP_VERSION:?}" "${BUILD_TIME:?}"
[[ "$DEPLOY_SHA" =~ ^[0-9a-f]{40}$ ]]
[[ "$IMAGE" =~ ^registry.digitalocean.com/compass/compass-backend:$DEPLOY_SHA@sha256:[0-9a-f]{64}$ ]]
release=/opt/compass/releases/$DEPLOY_SHA
cd "$release"
export COMPASS_IMAGE="$IMAGE" COMPASS_SECRETS_DIR=/opt/compass/secrets
# Never inherit the old selector's multi-file reset overlay or a caller's project/profile.
unset COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PROFILES
compose=(docker compose --project-name compass --profile realtime -f "$release/compose.staging.yaml")
if [[ "${1:-}" == preflight ]]; then
  python3 deploy/runtime-secrets/check-runtime-secrets.py --secrets-dir /opt/compass/secrets --env-file /opt/compass/.env --owner compass >&2
  "${compose[@]}" config --format json > .candidate-config.json
  python3 deploy/staging/host_preflight.py .candidate-config.json | tee .host-preflight.json
  exit
fi
[[ "${1:-}" == deploy ]]
exec 9>/opt/compass/.live-reset.lock
flock -n 9
phase=preflight
cleanup() {
  result=$?
  trap - EXIT
  if [[ "$result" != 0 && "$phase" == quiescing ]]; then
    # Database untouched: resume precisely the old containers, without changing their manifests.
    python3 - <<'PY'
import json,subprocess
for container in json.load(open('.host-preflight.json'))['app_containers'].values():
    subprocess.run(['docker','update','--restart=unless-stopped',container],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['docker','start',container],check=True,stdout=subprocess.DEVNULL)
PY
  elif [[ "$result" != 0 && "$phase" == migrating ]]; then
    echo 'Deployment stopped after migration boundary. Keep app services stopped; no automatic image/SQL rollback.' >&2
    "${compose[@]}" stop --timeout -1 web worker beat realtime proxy || true
  fi
  rm -f .candidate-config.json .host-preflight.locked.json
  rm -rf .registry
  exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# Repeat immediately under the host lock; an earlier read is not permission to ignore drift.
python3 deploy/runtime-secrets/check-runtime-secrets.py --secrets-dir /opt/compass/secrets --env-file /opt/compass/.env --owner compass
"${compose[@]}" config --format json > .candidate-config.json
python3 deploy/staging/host_preflight.py .candidate-config.json > .host-preflight.locked.json
python3 - <<'CHECK_SNAPSHOT'
import json
before=json.load(open('.host-preflight.json')); locked=json.load(open('.host-preflight.locked.json'))
assert all(before[key]==locked[key] for key in ['current_revision','current_image','app_containers']), 'Runtime changed after lineage approval'
CHECK_SNAPSHOT
mv .host-preflight.locked.json .host-preflight.json
export DOCKER_CONFIG="$release/.registry"
docker pull "$IMAGE"
python3 - "$IMAGE" "$DEPLOY_SHA" "$APP_VERSION" "$BUILD_TIME" <<'PY'
import json,subprocess,sys
labels=json.loads(subprocess.check_output(['docker','image','inspect',sys.argv[1]]))[0]['Config']['Labels']
assert all(labels.get(k)==v for k,v in zip(['org.opencontainers.image.revision','org.opencontainers.image.version','org.opencontainers.image.created'],sys.argv[2:])), 'Image metadata mismatch'
PY
# Candidate database/plan probe runs SELECT-only before downtime or migrations.
"${compose[@]}" run --rm --no-deps --pull never -T web python deploy/staging/database_preflight.py </dev/null
python3 - <<'PY'
import json,subprocess
s=json.load(open('.host-preflight.json'));subprocess.run(['docker','image','inspect',s['current_image']],check=True,stdout=subprocess.DEVNULL)
PY
phase=quiescing
# Stop producers first, allow in-flight HTTP requests to finish, leave the worker alive to drain.
python3 - <<'PY'
import json,subprocess
s=json.load(open('.host-preflight.json'))['app_containers']
subprocess.run(['docker','stop','--timeout','-1',*[s[k] for k in ('proxy','web','beat','realtime') if k in s]],check=True)
PY
# Use the old running worker's code/config with the candidate's read-only inspection script.
docker exec -i compass-worker-1 python - worker-idle < deploy/staging/database_preflight.py
# Warm stop only: never force-kill an external provider operation.
docker stop --timeout -1 compass-worker-1
python3 - <<'PY'
import json,subprocess
s=json.load(open('.host-preflight.json'))
for name,cid in s['app_containers'].items():
    c=json.loads(subprocess.check_output(['docker','inspect',cid]))[0]
    assert not c['State']['Running'], 'Old application process remains'
PY
# No old process may be restarted by Docker across the schema boundary.
python3 - <<'FENCE_RESTARTS'
import json,subprocess
ids=list(json.load(open('.host-preflight.json'))['app_containers'].values())
subprocess.run(['docker','update','--restart=no',*ids],check=True)
FENCE_RESTARTS
# Recheck the plan after all old consumers have stopped; no stale-plan race.
"${compose[@]}" run --rm --no-deps --pull never -T web python deploy/staging/database_preflight.py </dev/null
phase=migrating
"${compose[@]}" run --rm --no-deps --pull never -T web python manage.py migrate --noinput </dev/null
for command in sync_identity_policy sync_canonical_services sync_institutional_forms sync_organization_catalog; do
  "${compose[@]}" run --rm --no-deps --pull never -T web python manage.py "$command" </dev/null
done
"${compose[@]}" run --rm --no-deps --pull never -T web python manage.py migrate --check </dev/null
"${compose[@]}" run --rm --no-deps --pull never -T web python manage.py check --deploy --database default </dev/null
# Preserve whether realtime was active. No --remove-orphans or implicit infrastructure startup.
apps=(web worker beat proxy)
realtime=$(python3 -c 'import json; print(str(json.load(open(".host-preflight.json"))["realtime"]).lower())')
[[ "$realtime" != true ]] || apps+=(realtime)
"${compose[@]}" up -d --no-deps --pull never --wait --wait-timeout 180 "${apps[@]}"
"${compose[@]}" exec -T web python manage.py compass_doctor --worker-smoke --worker-timeout 10
python3 - "$DEPLOY_SHA" "$APP_VERSION" "$BUILD_TIME" <<'PY'
import json,sys,urllib.request,subprocess
from pathlib import Path
with urllib.request.urlopen(urllib.request.Request('https://staging-api.compass-gco.com/api/v1/meta',headers={'Cache-Control':'no-cache'}),timeout=15) as r:
    meta=json.load(r)
assert meta['application']=='COMPASS' and meta['environment']=='live-staging'
assert [meta['build_id'],meta['version'],meta['built_at']]==sys.argv[1:]
# Check every actual app image, not only web's public response.
import os
expected_image=json.loads(subprocess.check_output(['docker','image','inspect',os.environ['COMPASS_IMAGE']]))[0]['Id']
for name in ['web','worker','beat']+(['realtime'] if json.load(open('.host-preflight.json'))['realtime'] else []):
    c=json.loads(subprocess.check_output(['docker','inspect','compass-'+name+'-1']))[0]
    image=json.loads(subprocess.check_output(['docker','image','inspect',c['Image']]))[0]
    assert c['Image']==expected_image and image['Config']['Labels']['org.opencontainers.image.revision']==sys.argv[1] and c['State']['Running']
PY
# Only a validated canonical selector becomes active. Preserve a refusal, not an old-image rollback.
printf 'COMPASS_IMAGE=%s\nCOMPASS_SECRETS_DIR=/opt/compass/secrets\nCOMPOSE_FILE=%s/compose.staging.yaml\nCOMPOSE_PROFILES=%s\n' "$IMAGE" "$release" "$([[ "$realtime" == true ]] && echo realtime || true)" > /opt/compass/.deploy.env.next
chmod 640 /opt/compass/.deploy.env.next
mv /opt/compass/.deploy.env.next /opt/compass/.deploy.env
printf 'echo "Automatic rollback is prohibited; use reviewed canonical forward recovery" >&2\nreturn 1\n' > /opt/compass/.deploy.previous.env
chmod 640 /opt/compass/.deploy.previous.env
phase=complete
echo "Canonical staging deployed: $DEPLOY_SHA (existing volumes preserved)"
