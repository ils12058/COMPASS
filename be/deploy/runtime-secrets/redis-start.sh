#!/bin/sh
# Deployment-owned wrapper for the official Redis image. Never enable shell tracing.
set -eu
umask 077
secret=/run/secrets/redis_password
if [ ! -f "$secret" ] || [ ! -r "$secret" ] || [ ! -s "$secret" ]; then
    echo 'redis_password: missing, unreadable, or empty' >&2
    exit 1
fi

read_password() {
    # Match config.env's UTF-8 text newline handling. Buffer line endings to discard
    # only trailing ones; hex-encode every remaining byte for Redis's quoted syntax.
    # od/awk are supplied by the official Debian Redis image; no extra image needed.
    LC_ALL=C od -An -v -tu1 "$secret" | LC_ALL=C awk -v output="$1" '
        function emit(b) {
            if (output == "hex") printf "\\x%02x", b;
            else printf "%c", b;
            count++;
        }
        {
            for (i = 1; i <= NF; i++) {
                b = $i;
                if (b == 0) exit 1;
                if (b == 13) { if (cr) endings++; cr = 1; continue; }
                if (b == 10) { endings++; cr = 0; continue; }
                if (cr) { endings++; cr = 0; }
                while (endings > 0) { emit(10); endings--; }
                emit(b);
            }
        }
        END { if (!count) exit 1; }
    '
}

case "${1:-start}" in
    healthcheck)
        REDISCLI_AUTH="$(read_password raw)" || exit 1
        export REDISCLI_AUTH
        redis-cli --no-auth-warning ping | grep -qx PONG
        ;;
    start)
        config=/run/redis-config/redis.conf
        # This path must be the dedicated tmpfs from compose.staging.yaml.
        if ! awk '$2 == "/run/redis-config" && $3 == "tmpfs" { found=1 } END { exit !found }' /proc/mounts; then
            echo 'Redis runtime configuration requires /run/redis-config tmpfs' >&2
            exit 1
        fi
        encoded="$(read_password hex)" || { echo 'redis_password: invalid or empty' >&2; exit 1; }
        printf 'appendonly yes\nrequirepass "%s"\n' "$encoded" > "$config"
        unset encoded
        chown redis:redis /run/redis-config "$config"
        chmod 0700 /run/redis-config
        chmod 0600 "$config"
        exec /usr/local/bin/docker-entrypoint.sh redis-server "$config"
        ;;
    *)
        echo 'Redis wrapper: unsupported mode' >&2
        exit 1
        ;;
esac
