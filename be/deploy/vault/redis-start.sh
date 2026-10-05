#!/bin/sh
# No password in container configuration or process arguments. Config exists only on tmpfs.
set -eu
umask 077
secret=/run/secrets/redis_password
if [ ! -r "$secret" ] || [ ! -s "$secret" ]; then
  echo 'Redis runtime credential is unavailable' >&2
  exit 1
fi
# Encode every byte as a Redis double-quoted hex escape (including quotes/backslashes).
# Agent renders no trailing newline; shell variables remain unexported.
encoded=$(od -An -v -tx1 "$secret" | tr -d '\n' | sed 's/  */ /g;s/^ //;s/ /\\x/g;s/^/\\x/')
mkdir -p /run/compass-redis
printf 'appendonly yes\nrequirepass "%s"\n' "$encoded" > /run/compass-redis/redis.conf
unset encoded
chown -R redis:redis /run/compass-redis
exec /usr/local/bin/docker-entrypoint.sh redis-server /run/compass-redis/redis.conf
