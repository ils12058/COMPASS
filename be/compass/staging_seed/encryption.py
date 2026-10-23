"""Secret-free preflight for every encrypted domain Staging Dataset v1 writes."""

from django.conf import settings

from compass.confidential_data.crypto import (
    decrypt_bound_json,
    encrypt_bound_json,
    parse_fernet_keyring,
)

from .support import StagingSeedError

REQUIRED_KEYRINGS = (
    "ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
    "FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
    "ROUTINE_INTERVIEW_ENCRYPTION_KEYS",
    "STUDENT_SESSION_SUMMARY_ENCRYPTION_KEYS",
    "REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
    "EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
    "INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
    "GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
    "GUIDANCE_MESSAGE_ENCRYPTION_KEYS",
)


def verify_encryption_keyrings() -> None:
    for name in REQUIRED_KEYRINGS:
        try:
            ring = parse_fernet_keyring(getattr(settings, name, ""), setting=name)
            token = encrypt_bound_json(
                keyring=ring, schema_version=1, binding={"domain": name}, payload={"probe": True}
            )
            if decrypt_bound_json(
                token, keyring=ring, schema_version=1, binding={"domain": name}
            ) != {"probe": True}:
                raise ValueError("keyring round trip failed")
        except Exception:
            raise StagingSeedError(
                f"{name} is missing or unusable; configure the domain keyring "
                "before seeding. No encryption keys were generated."
            ) from None
