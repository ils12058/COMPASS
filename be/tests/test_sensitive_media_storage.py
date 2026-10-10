"""Private storage configuration and deletion contract, entirely fake S3 calls."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from compass.integrations.sensitive_storage import (
    SensitiveMediaStorage,
    SensitiveStoragePolicyError,
)
from compass.integrations.storage import ObjectStorage


def no_config(code):
    return ClientError({"Error": {"Code": code}}, "test")


def backend():
    storage = SensitiveMediaStorage(bucket_name="synthetic-private", location="e-counseling")
    client = MagicMock()
    client.get_bucket_versioning.return_value = {}
    client.get_bucket_acl.return_value = {"Grants": [{"Grantee": {"Type": "CanonicalUser"}}]}
    client.get_bucket_policy.side_effect = no_config("NoSuchBucketPolicy")
    client.get_bucket_lifecycle_configuration.side_effect = no_config(
        "NoSuchLifecycleConfiguration"
    )
    storage._connections.connection = SimpleNamespace(meta=SimpleNamespace(client=client))
    return storage, client


@pytest.mark.parametrize("versioning", ["Enabled", "Suspended"])
def test_versioned_buckets_are_rejected_including_suspended_old_versions(versioning):
    storage, client = backend()
    client.get_bucket_versioning.return_value = {"Status": versioning}
    with pytest.raises(SensitiveStoragePolicyError):
        storage.validate_sensitive_policy()


@pytest.mark.parametrize(
    "policy",
    [
        {"Effect": "Allow", "Principal": "*"},
        {"Effect": "Allow", "Principal": {"AWS": ["*"]}},
        {"Effect": "Allow", "NotPrincipal": {"AWS": "some-identity"}},
    ],
)
def test_public_policy_is_rejected(policy):
    storage, client = backend()
    client.get_bucket_policy.side_effect = None
    client.get_bucket_policy.return_value = {"Policy": json.dumps({"Statement": [policy]})}
    with pytest.raises(SensitiveStoragePolicyError):
        storage.validate_sensitive_policy()


def test_public_acl_and_overlapping_expiration_are_rejected():
    storage, client = backend()
    client.get_bucket_acl.return_value = {"Grants": [{"Grantee": {"Type": "Group"}}]}
    with pytest.raises(SensitiveStoragePolicyError):
        storage.validate_sensitive_policy()
    client.get_bucket_acl.return_value = {"Grants": []}
    client.get_bucket_lifecycle_configuration.side_effect = None
    client.get_bucket_lifecycle_configuration.return_value = {
        "Rules": [
            {"Status": "Enabled", "Filter": {"Prefix": "e-counseling/"}, "Expiration": {"Days": 30}}
        ]
    }
    with pytest.raises(SensitiveStoragePolicyError):
        storage.validate_sensitive_policy()


def test_unversioned_private_storage_without_expiration_passes():
    storage, client = backend()
    storage.validate_sensitive_policy()
    assert storage.default_acl == "private" and storage.querystring_auth
    assert storage.custom_domain is None and storage.file_overwrite
    assert storage.object_parameters == {"CacheControl": "private, no-store"}


def test_policy_read_failure_is_sanitized_and_fails_closed():
    storage, client = backend()
    client.get_bucket_versioning.side_effect = RuntimeError("secret endpoint and credential")
    with pytest.raises(SensitiveStoragePolicyError) as caught:
        storage.validate_sensitive_policy()
    assert "secret" not in str(caught.value)


def test_safe_download_headers_and_old_url_call_remain_compatible():
    configured = MagicMock()
    storage = ObjectStorage(configured)
    storage.private_url("opaque", expires_seconds=300)
    configured.url.assert_called_with("opaque", expire=300)
    storage.private_url(
        "opaque",
        expires_seconds=300,
        filename="e-counseling-recording.mp4",
        content_type="video/mp4",
    )
    configured.url.assert_called_with(
        "opaque",
        expire=300,
        parameters={
            "ResponseContentDisposition": 'attachment; filename="e-counseling-recording.mp4"',
            "ResponseContentType": "video/mp4",
        },
    )
    for filename in ("name\r\nInjected: secret", "../name", 'name".vtt'):
        with pytest.raises(ValueError):
            storage.private_url("opaque", expires_seconds=300, filename=filename)


def test_digest_verification_reads_chunks_and_rejects_truncation_or_surplus():
    import hashlib

    configured = MagicMock()
    configured.iter_chunks.return_value = iter([b"syn", b"thetic"])
    assert ObjectStorage(configured).verify(
        "opaque", size=9, sha256=hashlib.sha256(b"synthetic").hexdigest()
    )
    configured.iter_chunks.return_value = iter([b"truncated"])
    assert not ObjectStorage(configured).verify("opaque", size=20, sha256="0" * 64)
    configured.iter_chunks.return_value = iter([b"surplus"])
    assert not ObjectStorage(configured).verify("opaque", size=1, sha256="0" * 64)


def test_sensitive_save_uses_exact_uuid_key_without_generic_name_renaming():
    from unittest.mock import patch

    storage, _ = backend()
    key = (
        "11111111-1111-4111-8111-111111111111/"
        "22222222-2222-4222-8222-222222222222/"
        "33333333-3333-4333-8333-333333333333"
    )
    with patch.object(storage, "_save", return_value=key) as save:
        from django.core.files.base import ContentFile

        assert storage.save(key, ContentFile(b"synthetic")) == key
    save.assert_called_once()
    for invalid in ("../opaque", "patient-name.mp4", key + "/extra", key.replace("/", "//", 1)):
        with pytest.raises(SensitiveStoragePolicyError):
            storage.save(invalid, ContentFile(b"synthetic"))


def test_storage_namespace_identity_tracks_location_but_allows_credential_rotation():
    storage, _ = backend()
    identity = storage.binding_identity()
    storage.access_key = "rotated"
    storage.secret_key = "rotated"
    assert storage.binding_identity() == identity
    storage.bucket_name = "different-bucket"
    assert storage.binding_identity() != identity
    storage.bucket_name = "synthetic-private"
    storage.location = "other-prefix"
    assert storage.binding_identity() != identity
    storage.location = "e-counseling"
    storage.endpoint_url = "https://other-endpoint.invalid"
    assert storage.binding_identity() != identity
