#!/bin/sh
# Host preflight: checks metadata only; never read or print secret contents.
set -eu
for unit in vault.service vault-agent.service; do
  if ! systemctl is-active --quiet "$unit"; then
    echo "Runtime secret service is inactive: $unit" >&2
    exit 1
  fi
done
if ! curl --fail --silent --output /dev/null --max-time 5 \
  --cacert /etc/vault.d/tls/ca.crt https://127.0.0.1:8200/v1/sys/health; then
  echo 'Vault is not ready and unsealed' >&2
  exit 1
fi
for name in django_secret_key postgres_password redis_password s3_access_key_id \
  s3_secret_access_key auth_totp_encryption_key routine_interview_encryption_keys; do
  if [ ! -f "/run/compass-secrets/$name" ] || [ ! -r "/run/compass-secrets/$name" ] || \
    [ ! -s "/run/compass-secrets/$name" ]; then
    echo "Required runtime secret file is unavailable: $name" >&2
    exit 1
  fi
done
# Disabled integrations may deliberately render empty files. Django still enforces each enabled
# feature's requirements. Every pointer must be backed by a readable regular file.
for name in smtp_username smtp_password turnstile_secret_key daily_api_key daily_webhook_hmac \
  psgc_api_token web_push_private_key web_push_storage_key; do
  if [ ! -f "/run/compass-secrets/$name" ] || [ ! -r "/run/compass-secrets/$name" ]; then
    echo "Runtime secret file is unavailable: $name" >&2
    exit 1
  fi
done
for name in django_secret_key postgres_password redis_password s3_access_key_id s3_secret_access_key \
  auth_totp_encryption_key routine_interview_encryption_keys smtp_username smtp_password \
  turnstile_secret_key daily_api_key daily_webhook_hmac psgc_api_token web_push_private_key \
  web_push_storage_key; do
  if [ -L "/run/compass-secrets/$name" ] || \
    [ "$(stat -c '%a:%g' "/run/compass-secrets/$name")" != '440:1900' ]; then
    echo "Runtime secret file permissions are invalid: $name" >&2
    exit 1
  fi
done
echo 'Runtime secret services and files are ready'
