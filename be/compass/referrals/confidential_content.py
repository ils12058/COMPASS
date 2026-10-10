"""Explicit Referral-domain content policy and bound envelopes (ADR-081)."""

from dataclasses import asdict, dataclass
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from compass.confidential_data import crypto
from compass.confidential_data.errors import ConfidentialDataUnavailable, UnavailableReason

from .errors import InvalidReferralInput, ReferralError
from .models import Referral, ReferralAction, ReferralActionType

KEYRING_SETTING = "REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"
REFERRAL_SCHEMA_VERSION = 1
ACTION_SCHEMA_VERSION = 1
CONTENT_LIMITS = {
    "reason": 10_000,
    "referrer_name": 255,
    "status_note": 1_000,
    "void_reason": 1_000,
}
MAX_REMARKS_LENGTH = 4_000


@dataclass(frozen=True, slots=True)
class ReferralConfidentialContent:
    reason: str
    referrer_name: str
    status_note: str = ""
    void_reason: str = ""


class ReferralConfidentialContentUnavailable(ReferralError):
    def __init__(
        self,
        *,
        referral_id: UUID,
        reason: UnavailableReason,
        referral_action_id: UUID | None = None,
        action_type: str | None = None,
    ):
        ConfidentialDataUnavailable(reason=reason)
        super().__init__("The Referral confidential content is unavailable.")
        self.referral_id = referral_id
        self.referral_action_id = referral_action_id
        self.action_type = action_type if action_type in ReferralActionType.values else None
        self.reason = reason


def validate_text(value: str, *, label: str, max_length: int, required: bool = False) -> str:
    """Validate without normalization, so verified historical text remains byte-faithful."""
    if not isinstance(value, str):
        raise InvalidReferralInput(f"{label} must be text.")
    if "\x00" in value:
        raise InvalidReferralInput(f"{label} must not contain NUL.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise InvalidReferralInput(f"{label} must be UTF-8 text.") from None
    if required and not value.strip():
        raise InvalidReferralInput(f"{label} is required.")
    if len(value) > max_length:
        raise InvalidReferralInput(f"{label} is too long.")
    return value


def _content(payload: dict[str, object], *, voided: bool) -> ReferralConfidentialContent:
    if set(payload) != set(CONTENT_LIMITS):
        raise InvalidReferralInput("The Referral content payload is invalid.")
    for name, limit in CONTENT_LIMITS.items():
        validate_text(
            payload[name],
            label=name,
            max_length=limit,
            required=name in {"reason", "referrer_name"} or (name == "void_reason" and voided),
        )
    if not voided and payload["void_reason"] != "":
        raise InvalidReferralInput("An active Referral must have an empty void_reason.")
    return ReferralConfidentialContent(**payload)


def _keyring():
    try:
        return crypto.parse_fernet_keyring(
            getattr(settings, KEYRING_SETTING, ""), setting=KEYRING_SETTING
        )
    except ValueError as exc:
        raise ImproperlyConfigured(str(exc)) from None


def _binding(item):
    binding = {
        "referral_id": str(item.referral_id if isinstance(item, ReferralAction) else item.pk)
    }
    if isinstance(item, ReferralAction):
        binding.update(referral_action_id=str(item.pk), action_type=item.action_type)
    return binding


def _unavailable(item, reason):
    return ReferralConfidentialContentUnavailable(
        referral_id=item.referral_id if isinstance(item, ReferralAction) else item.pk,
        referral_action_id=item.pk if isinstance(item, ReferralAction) else None,
        action_type=item.action_type if isinstance(item, ReferralAction) else None,
        reason=reason,
    )


def _decrypt(item, token, schema_version):
    if not isinstance(token, str) or not token:
        raise _unavailable(item, "missing")
    try:
        return crypto.decrypt_bound_json(
            token, keyring=_keyring(), schema_version=schema_version, binding=_binding(item)
        )
    except ConfidentialDataUnavailable as exc:
        raise _unavailable(item, exc.reason) from None


def read_referral_confidential_content(item: Referral) -> ReferralConfidentialContent:
    payload = _decrypt(item, item.confidential_content_ciphertext, REFERRAL_SCHEMA_VERSION)
    try:
        return _content(payload, voided=item.voided_at is not None)
    except InvalidReferralInput:
        raise _unavailable(item, "malformed") from None


def write_referral_confidential_content(
    item: Referral, content: ReferralConfidentialContent
) -> None:
    payload = asdict(content)
    _content(payload, voided=item.voided_at is not None)
    item.confidential_content_ciphertext = crypto.encrypt_bound_json(
        keyring=_keyring(),
        schema_version=REFERRAL_SCHEMA_VERSION,
        binding=_binding(item),
        payload=payload,
    )


def read_referral_action_remarks(action: ReferralAction) -> str:
    payload = _decrypt(action, action.remarks_ciphertext, ACTION_SCHEMA_VERSION)
    try:
        if set(payload) != {"remarks"}:
            raise InvalidReferralInput("The Referral action payload is invalid.")
        return validate_text(payload["remarks"], label="remarks", max_length=MAX_REMARKS_LENGTH)
    except InvalidReferralInput:
        raise _unavailable(action, "malformed") from None


def write_referral_action_remarks(action: ReferralAction, remarks: str) -> None:
    validate_text(remarks, label="remarks", max_length=MAX_REMARKS_LENGTH)
    action.remarks_ciphertext = crypto.encrypt_bound_json(
        keyring=_keyring(),
        schema_version=ACTION_SCHEMA_VERSION,
        binding=_binding(action),
        payload={"remarks": remarks},
    )


def encrypted_with_primary_key(token: str) -> bool:
    return crypto.encrypted_with_primary_key(token, keyring=_keyring())


def reencrypt_referral_content(item: Referral) -> str:
    read_referral_confidential_content(item)
    return crypto.reencrypt_with_primary_key(
        item.confidential_content_ciphertext, keyring=_keyring()
    )


def reencrypt_referral_action_remarks(action: ReferralAction) -> str:
    read_referral_action_remarks(action)
    return crypto.reencrypt_with_primary_key(action.remarks_ciphertext, keyring=_keyring())
