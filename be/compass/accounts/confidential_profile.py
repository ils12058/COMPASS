"""Explicit Accounts current-profile envelopes (ADR-085); never implicit ORM decryption."""

from dataclasses import asdict, dataclass
from datetime import date
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from compass.confidential_data import crypto
from compass.confidential_data.errors import ConfidentialDataUnavailable, UnavailableReason

KEYRING_SETTING = "ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"
COLUMN = "profile_confidential_content_ciphertext"
TEXT_LIMITS = {
    "civil_status": 80,
    "contact_number": 64,
    "current_address": 2000,
    "permanent_address": 2000,
}


@dataclass(frozen=True, slots=True)
class AccountProfileConfidentialContent:
    date_of_birth: date | None = None
    civil_status: str = ""
    contact_number: str = ""
    current_address: str = ""
    permanent_address: str = ""


class AccountProfileConfidentialContentUnavailable(RuntimeError):
    def __init__(self, *, user_id: UUID, reason: UnavailableReason):
        ConfidentialDataUnavailable(reason=reason)
        super().__init__("The account profile confidential content is unavailable.")
        self.user_id, self.reason = user_id, reason


def _keyring():
    try:
        return crypto.parse_fernet_keyring(
            getattr(settings, KEYRING_SETTING, ""), setting=KEYRING_SETTING
        )
    except ValueError as exc:
        raise ImproperlyConfigured(str(exc)) from None


def _content(payload):
    if set(payload) != {"date_of_birth", *TEXT_LIMITS}:
        raise ValueError("Invalid profile payload.")
    birthday = payload["date_of_birth"]
    if birthday is not None:
        if not isinstance(birthday, str):
            raise ValueError("Invalid profile date.")
        parsed = date.fromisoformat(birthday)
        if parsed.isoformat() != birthday:
            raise ValueError("Invalid profile date.")
    else:
        parsed = None
    for name, limit in TEXT_LIMITS.items():
        value = payload[name]
        if not isinstance(value, str) or len(value) > limit or "\x00" in value:
            raise ValueError("Invalid profile text.")
        value.encode("utf-8")
    return AccountProfileConfidentialContent(**{**payload, "date_of_birth": parsed})


def read_account_profile_confidential_content(user):
    try:
        payload = crypto.decrypt_bound_json(
            getattr(user, COLUMN),
            keyring=_keyring(),
            schema_version=1,
            binding={"user_id": str(user.pk)},
        )
        return _content(payload)
    except ConfidentialDataUnavailable as exc:
        raise AccountProfileConfidentialContentUnavailable(
            user_id=user.pk, reason=exc.reason
        ) from None
    except (ValueError, TypeError, UnicodeEncodeError):
        raise AccountProfileConfidentialContentUnavailable(
            user_id=user.pk, reason="malformed"
        ) from None


def write_account_profile_confidential_content(user, content: AccountProfileConfidentialContent):
    payload = asdict(content)
    birthday = payload["date_of_birth"]
    if birthday is not None and type(birthday) is not date:
        raise ValueError("Invalid profile date.")
    payload["date_of_birth"] = birthday.isoformat() if birthday is not None else None
    _content(payload)
    setattr(
        user,
        COLUMN,
        crypto.encrypt_bound_json(
            keyring=_keyring(), schema_version=1, binding={"user_id": str(user.pk)}, payload=payload
        ),
    )


def encrypted_with_primary_key(token):
    return crypto.encrypted_with_primary_key(token, keyring=_keyring())


def reencrypt_account_profile_confidential_content(user):
    read_account_profile_confidential_content(user)
    return crypto.reencrypt_with_primary_key(getattr(user, COLUMN), keyring=_keyring())
