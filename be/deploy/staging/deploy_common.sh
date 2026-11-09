#!/usr/bin/env bash
# Shared post-start verification and atomic selector publication. Source only.
verify_running_release() {
python3 - "$DEPLOY_SHA" "$APP_VERSION" "$BUILD_TIME" <<'PY'
import json,sys,urllib.request,subprocess
from pathlib import Path
with urllib.request.urlopen(urllib.request.Request('https://staging-api.compass-gco.com/api/v1/meta',headers={'Cache-Control':'no-cache','User-Agent':'COMPASS-Staging-Deploy/1.0'}),timeout=15) as r:
    meta=json.load(r)
assert meta['application']=='COMPASS' and meta['environment']=='live-staging'
assert [meta['build_id'],meta['version'],meta['built_at']]==sys.argv[1:]
# Check every actual app image, not only web's public response.
import os
expected_image=json.loads(subprocess.check_output(['docker','image','inspect',os.environ['COMPASS_IMAGE']]))[0]['Id']
for name in ['web','worker','beat','realtime']:
    c=json.loads(subprocess.check_output(['docker','inspect','compass-'+name+'-1']))[0]
    image=json.loads(subprocess.check_output(['docker','image','inspect',c['Image']]))[0]
    assert c['Image']==expected_image and image['Config']['Labels']['org.opencontainers.image.revision']==sys.argv[1] and c['State']['Running']
PY

}
publish_selector() {
# Only a validated canonical selector becomes active. Preserve a refusal, not an old-image rollback.
printf 'COMPASS_IMAGE=%s\nCOMPASS_SECRETS_DIR=/opt/compass/secrets\nCOMPOSE_FILE=%s/compose.staging.yaml\n' "$IMAGE" "$release" > /opt/compass/.deploy.env.next
chmod 640 /opt/compass/.deploy.env.next
mv /opt/compass/.deploy.env.next /opt/compass/.deploy.env
printf 'echo "Automatic rollback is prohibited; use reviewed canonical forward recovery" >&2\nreturn 1\n' > /opt/compass/.deploy.previous.env
chmod 640 /opt/compass/.deploy.previous.env
}
