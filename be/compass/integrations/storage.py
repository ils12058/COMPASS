"""Small application-facing object-storage boundary."""

from __future__ import annotations

import hashlib
import re

from django.core.files.storage import Storage, storages


class ObjectStorage:
    """Delegate object operations to Django's configured S3-compatible storage."""

    def __init__(self, backend: Storage | None = None, *, alias: str = "default") -> None:
        self.backend = backend if backend is not None else storages[alias]

    def save(self, name: str, content) -> str:
        return self.backend.save(name, content)

    def open(self, name: str, mode: str = "rb"):
        return self.backend.open(name, mode)

    def exists(self, name: str) -> bool:
        return self.backend.exists(name)

    def delete(self, name: str) -> None:
        self.backend.delete(name)

    def url(self, name: str) -> str:
        return self.backend.url(name)

    def private_url(
        self,
        name: str,
        *,
        expires_seconds: int,
        filename: str | None = None,
        content_type: str | None = None,
        disposition: str = "attachment",
    ) -> str:
        """Return time-bounded private access from the configured S3-compatible backend."""

        if type(expires_seconds) is not int or expires_seconds <= 0:
            raise ValueError("expires_seconds must be a positive integer")
        parameters = {}
        if filename is not None:
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", filename):
                raise ValueError("Unsafe download filename")
            if disposition not in {"attachment", "inline"}:
                raise ValueError("Unsupported disposition")
            parameters["ResponseContentDisposition"] = f'{disposition}; filename="{filename}"'
        if content_type is not None:
            if not re.fullmatch(r"[a-z0-9.+-]+/[a-z0-9.+-]+", content_type):
                raise ValueError("Unsafe content type")
            parameters["ResponseContentType"] = content_type
        if parameters:
            return self.backend.url(name, expire=expires_seconds, parameters=parameters)
        return self.backend.url(name, expire=expires_seconds)

    def validate_sensitive_policy(self) -> None:
        """Fail closed unless the backend can verify the sensitive live-copy contract."""
        self.backend.validate_sensitive_policy()

    def verify(self, name: str, *, size: int, sha256: str) -> bool:
        digest = hashlib.sha256()
        total = 0
        for chunk in self.backend.iter_chunks(name):
            total += len(chunk)
            if total > size:
                return False
            digest.update(chunk)
        return total == size and digest.hexdigest() == sha256
