"""The realtime service runs without Django, PostgreSQL, or confidential keyrings (ADR-100).

Each check starts a fresh interpreter whose environment holds only what the realtime container
receives: Redis location and the allowed browser Origins. No settings module, database
configuration, application secret, or encryption keyring is present.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest
import redis
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from realtime_service import protocol

BACKEND = Path(__file__).parents[1]
ORIGIN = "https://staging.compass-gco.com"
ALLOWED_MODULES = {
    "compass",
    "compass.common",
    "compass.common.config",
    "compass.common.redis_config",
}


def reduced_environment() -> dict[str, str]:
    environment = {
        "PATH": os.environ["PATH"],
        "APP_ENV": "local-staging",
        "REDIS_REALTIME_URL": os.environ["REDIS_REALTIME_URL"],
        "REALTIME_ALLOWED_ORIGINS": ORIGIN,
        # The image sets a settings module for the Django services; the realtime container
        # blanks it so any accidental settings access fails instead of loading Django.
        "DJANGO_SETTINGS_MODULE": "",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    forbidden = ("POSTGRES", "SECRET_KEY", "ENCRYPTION_KEY", "DATABASE")
    assert not any(marker in name for name in environment for marker in forbidden)
    return environment


def run_python(source: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=BACKEND,
        env=reduced_environment(),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_service_imports_without_django_or_domain_code():
    output = run_python(
        "import json, sys\n"
        "import realtime_service.app, realtime_service.store, realtime_service.config\n"
        "print(json.dumps(sorted(sys.modules)))\n"
    )
    loaded = set(json.loads(output))
    roots = {name.split(".")[0] for name in loaded}
    assert not roots & {"django", "ninja", "psycopg", "config", "celery"}
    compass_modules = {name for name in loaded if name.split(".")[0] == "compass"}
    assert compass_modules <= ALLOWED_MODULES, compass_modules - ALLOWED_MODULES
    # redis-py only probes that the cryptography package exists; no Fernet keyring code loads.
    assert not {name for name in loaded if name.startswith("cryptography.fernet")}


def test_service_starts_and_reports_ready_without_database_or_keyrings():
    output = run_python(
        "import asyncio, json, sys\n"
        "from realtime_service.app import app\n"
        "async def main():\n"
        "    queue = asyncio.Queue()\n"
        "    queue.put_nowait({'type': 'lifespan.startup'})\n"
        "    events = []\n"
        "    async def send(message):\n"
        "        events.append(message['type'])\n"
        "    task = asyncio.create_task(app({'type': 'lifespan'}, queue.get, send))\n"
        "    while not events:\n"
        "        await asyncio.sleep(0.01)\n"
        "    sent = []\n"
        "    async def receive():\n"
        "        return {'type': 'http.request', 'body': b''}\n"
        "    async def http_send(message):\n"
        "        sent.append(message)\n"
        "    scope = {'type': 'http', 'method': 'GET', 'path': '/api/realtime/v1/health/ready'}\n"
        "    await app(scope, receive, http_send)\n"
        "    queue.put_nowait({'type': 'lifespan.shutdown'})\n"
        "    await task\n"
        "    print(json.dumps({'events': events, 'status': sent[0]['status'],\n"
        "        'django': any(m.split('.')[0] == 'django' for m in sys.modules)}))\n"
        "asyncio.run(main())\n"
    )
    result = json.loads(output.strip().splitlines()[-1])
    assert result == {
        "events": ["lifespan.startup.complete", "lifespan.shutdown.complete"],
        "status": 200,
        "django": False,
    }


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _get(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def _mint(client: redis.Redis) -> str:
    ticket = secrets.token_urlsafe(protocol.TICKET_BYTES)
    who = protocol.SocketIdentity(user_id=str(uuid.uuid4()), session_id=str(uuid.uuid4()))
    metadata = protocol.encode_ticket_metadata(who, expires_at=int(time.time()) + 30)
    assert client.set(protocol.ticket_key(ticket), metadata, nx=True, ex=30)
    return ticket


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal handling")
def test_uvicorn_process_serves_health_origin_policy_tickets_and_shuts_down_cleanly():
    port = _free_port()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "realtime_service.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--ws",
            "websockets-sansio",
            "--ws-max-size",
            "4096",
            "--lifespan",
            "on",
            "--log-level",
            "warning",
            "--no-access-log",
            "--timeout-graceful-shutdown",
            "5",
        ],
        cwd=BACKEND,
        env=reduced_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    base = f"http://127.0.0.1:{port}"
    socket_url = f"ws://127.0.0.1:{port}{protocol.SOCKET_PATH}"
    client = redis.Redis.from_url(os.environ["REDIS_REALTIME_URL"], decode_responses=True)
    ticket = _mint(client)
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                if _get(base + protocol.HEALTH_LIVE_PATH)[0] == 200:
                    break
            except OSError:
                pass
            assert process.poll() is None, process.communicate()[1]
            assert time.monotonic() < deadline, "realtime service did not start"
            time.sleep(0.1)
        assert _get(base + protocol.HEALTH_READY_PATH) == (200, b'{"status":"ok"}')

        async def exercise() -> int:
            with pytest.raises(InvalidStatus) as rejected:
                async with connect(socket_url, origin="https://evil.example"):
                    pass
            assert rejected.value.response.status_code == 403

            async with connect(socket_url, origin=ORIGIN) as first:
                await first.send(json.dumps({"type": "authenticate", "ticket": ticket}))
                assert json.loads(await first.recv()) == {"v": 1, "type": "ready"}

                async with connect(socket_url, origin=ORIGIN) as second:
                    await second.send(json.dumps({"type": "authenticate", "ticket": ticket}))
                    with pytest.raises(ConnectionClosed) as reused:
                        await second.recv()
                    assert reused.value.rcvd.code == 4401

                # A restart ends live sockets; the browser reconnects with a fresh ticket.
                process.send_signal(signal.SIGTERM)
                with pytest.raises(ConnectionClosed) as restarted:
                    await asyncio.wait_for(first.recv(), 10)
                return restarted.value.rcvd.code

        assert asyncio.run(exercise()) == 1012
        stdout, stderr = process.communicate(timeout=15)
        # Uvicorn finishes its graceful shutdown, then re-raises the captured SIGTERM.
        assert process.returncode in (0, -signal.SIGTERM), stderr
        logs = stdout + stderr
        assert "realtime_stopped" in logs
        assert ticket not in logs
        assert protocol.ticket_key(ticket) not in logs
        assert "socket_authenticated" in logs
        assert "redis://" not in logs
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()
        client.close()
