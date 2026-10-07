"""Private, unversioned S3-compatible media custody; never emits object locations in errors."""

import json
import uuid

from boto3.s3.transfer import TransferConfig
from botocore.config import Config
from botocore.exceptions import ClientError
from django.core.files import File
from storages.backends.s3 import S3Storage


class SensitiveStoragePolicyError(RuntimeError):
    pass


def _has_wildcard(value):
    if isinstance(value, dict):
        return any(_has_wildcard(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_wildcard(item) for item in value)
    return value == "*"


class SensitiveMediaStorage(S3Storage):
    def __init__(self, **options):
        options.update(
            default_acl="private",
            querystring_auth=True,
            custom_domain=None,
            file_overwrite=True,
            gzip=False,
            object_parameters={"CacheControl": "private, no-store"},
            client_config=Config(
                signature_version="s3v4",
                connect_timeout=10,
                read_timeout=30,
                retries={"max_attempts": 2},
                s3={"addressing_style": options.get("addressing_style", "virtual")},
            ),
            transfer_config=TransferConfig(
                use_threads=False,
                multipart_chunksize=8 * 1024 * 1024,
            ),
        )
        super().__init__(**options)

    def save(self, name, content, max_length=None):
        # This alias accepts only canonical UUID paths. Bypass Storage's name-renaming flow:
        # S3's pinned _save writes exactly the precommitted key, including overwrite recovery.
        try:
            parts = name.split("/")
            valid = len(parts) == 3 and all(str(uuid.UUID(part)) == part for part in parts)
        except (ValueError, AttributeError):
            valid = False
        if not valid or max_length is not None and len(name) > max_length:
            raise SensitiveStoragePolicyError("Sensitive media storage identity is invalid.")
        if not hasattr(content, "chunks"):
            content = File(content)
        return self._save(name, content)

    def validate_sensitive_policy(self):
        client = self.connection.meta.client
        try:
            versioning = client.get_bucket_versioning(Bucket=self.bucket_name)
            # Suspended may retain old versions. Only a never-versioned bucket is accepted.
            if versioning.get("Status"):
                raise SensitiveStoragePolicyError("Sensitive storage versioning is unsupported.")
            acl = client.get_bucket_acl(Bucket=self.bucket_name)
            if any(
                grant.get("Grantee", {}).get("Type") == "Group" for grant in acl.get("Grants", [])
            ):
                raise SensitiveStoragePolicyError("Sensitive storage must be private.")
            try:
                policy = json.loads(client.get_bucket_policy(Bucket=self.bucket_name)["Policy"])
            except ClientError as exc:
                if exc.response["Error"]["Code"] != "NoSuchBucketPolicy":
                    raise
            else:
                statements = policy.get("Statement", [])
                if isinstance(statements, dict):
                    statements = [statements]
                if any(
                    row.get("Effect") == "Allow"
                    and (_has_wildcard(row.get("Principal")) or "NotPrincipal" in row)
                    for row in statements
                ):
                    raise SensitiveStoragePolicyError("Sensitive storage policy must be private.")
            try:
                lifecycle = client.get_bucket_lifecycle_configuration(Bucket=self.bucket_name)
            except ClientError as exc:
                if exc.response["Error"]["Code"] != "NoSuchLifecycleConfiguration":
                    raise
            else:
                for row in lifecycle.get("Rules", []):
                    prefix = row.get("Filter", {}).get("Prefix", row.get("Prefix", ""))
                    governed = self.location.rstrip("/") + "/"
                    if (
                        row.get("Status") == "Enabled"
                        and (governed.startswith(prefix) or prefix.startswith(governed))
                        and any(key in row for key in ("Expiration", "NoncurrentVersionExpiration"))
                    ):
                        raise SensitiveStoragePolicyError(
                            "Sensitive media cannot use age-based storage expiration."
                        )
        except SensitiveStoragePolicyError:
            raise
        except Exception:
            raise SensitiveStoragePolicyError(
                "Sensitive storage policy could not be verified."
            ) from None

    def iter_chunks(self, name):
        key = self._normalize_name(name)
        body = self.bucket.Object(key).get()["Body"]
        try:
            while chunk := body.read(64 * 1024):
                yield chunk
        finally:
            body.close()
