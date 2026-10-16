"""Operator-controlled credential issuance for Staging Dataset v1 participant accounts.

Seeding never sets a password. This separate, explicit step gives each selected participant
account its own random credential:

* passwords come from ``secrets`` and must pass the normal COMPASS password policy;
* only Django's password hash is stored; the plaintext is written once, to a *new* handoff file
  created with mode 0600 outside the repository, and is never printed, logged or audited;
* accounts that already have a usable password (issued earlier or changed by the participant) are
  skipped unless the operator names them with ``--account`` and confirms ``--reissue``; a reissue
  revokes the account's sessions, trusted browsers and pending email challenges;
* restricted accounts are issued only when named explicitly; disabled and onboarding accounts
  never are. MFA, email verification and authorization policy are unchanged.

The handoff file is the operator's responsibility: deliver each line privately to its evaluator,
then delete the file. Evaluator identities are never written here or in the repository.
"""

from __future__ import annotations

import csv
import io
import os
import secrets
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from compass.accounts.models import User
from compass.audit.context import AuditContext
from compass.audit.services import record_event
from compass.authentication.actions import AUTH_PASSWORD_INITIAL_SET, AUTH_PASSWORD_RESET
from compass.authentication.models import EmailOTPPurpose
from compass.authentication.security import invalidate_reusable_auth_state
from compass.common.correlation import reset_current_request_id, set_current_request_id

from .identities import AuthPlan, Suitability
from .manifest import ACCOUNTS, ACCOUNTS_BY_KEY

# Audit metadata only names the method; never the credential or the handoff path.
ISSUANCE_METHOD = "staging_operator_issuance"
REISSUE_METHOD = "staging_operator_reissue"
PASSWORD_BYTES = 18  # 24 URL-safe characters, well above the 15-character policy minimum.
HANDOFF_COLUMNS = ("account_key", "institutional_id", "email", "role", "temporary_password")


class CredentialIssuanceError(RuntimeError):
    """Issuance was refused; messages never contain a credential."""


@dataclass(frozen=True)
class IssuanceOutcome:
    issued: int
    skipped: int
    path: Path


def _repository_root() -> Path | None:
    try:
        top = subprocess.run(
            ["git", "-C", str(settings.BASE_DIR), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return (
        Path(top.stdout.strip()).resolve() if top.returncode == 0 and top.stdout.strip() else None
    )


def _validate_output(path: Path) -> Path:
    target = path.expanduser().resolve()
    protected = {Path(settings.BASE_DIR).resolve(), Path(settings.BASE_DIR).resolve().parent}
    repository = _repository_root()
    if repository is not None:
        protected.add(repository)
    if any(target == root or root in target.parents for root in protected):
        raise CredentialIssuanceError(
            "Refusing to write credentials inside the source tree; choose a protected path outside "
            "the repository (for example a mounted operator directory)."
        )
    if not target.parent.is_dir():
        raise CredentialIssuanceError("The handoff file's directory does not exist.")
    if target.exists():
        raise CredentialIssuanceError("The handoff file already exists; never overwrite one.")
    return target


def _generate(user: User) -> str:
    for _attempt in range(10):
        candidate = secrets.token_urlsafe(PASSWORD_BYTES)
        try:
            validate_password(candidate, user)
        except ValidationError:
            continue
        return candidate
    raise CredentialIssuanceError("Could not generate a policy-compliant credential.")


def _selected(account_keys: tuple[str, ...], reissue: bool):
    unknown = [key for key in account_keys if key not in ACCOUNTS_BY_KEY]
    if unknown:
        raise CredentialIssuanceError(f"Unknown dataset account key(s): {', '.join(unknown)}.")
    if reissue and not account_keys:
        raise CredentialIssuanceError("--reissue requires explicit --account keys.")
    if not account_keys:
        # Default: every UAT-ready credential account. Onboarding accounts keep their own flow.
        return [
            a
            for a in ACCOUNTS
            if a.suitability == Suitability.PARTICIPANT and a.auth == AuthPlan.CREDENTIAL
        ]
    accounts = [ACCOUNTS_BY_KEY[key] for key in account_keys]
    for account in accounts:
        if account.auth != AuthPlan.CREDENTIAL:
            reason = (
                "uses first-time onboarding"
                if account.auth == AuthPlan.ONBOARDING
                else ("is disabled")
            )
            raise CredentialIssuanceError(
                f"{account.key} {reason}; it never receives an issued credential."
            )
    return accounts


def issue_credentials(
    *,
    output: Path,
    account_keys: tuple[str, ...] = (),
    reissue: bool = False,
    confirm_reissue: bool = False,
) -> IssuanceOutcome:
    if reissue and not confirm_reissue:
        raise CredentialIssuanceError("A reissue revokes sessions; add --confirm-reissue.")
    target = _validate_output(output)
    accounts = _selected(account_keys, reissue)

    run_id = str(uuid.uuid4())
    token = set_current_request_id(run_id)
    context = AuditContext.system(request_id=run_id)
    rows: list[tuple[str, ...]] = []
    skipped = 0
    written = False
    try:
        from .seed import exclusive_dataset_operation

        with exclusive_dataset_operation(), transaction.atomic():
            users = {
                user.institutional_id: user
                for user in User.objects.select_for_update(of=("self",))
                .select_related("role")
                .filter(institutional_id__in=[a.institutional_id for a in accounts])
            }
            for account in accounts:
                user = users.get(account.institutional_id)
                if user is None or user.role.code != account.role:
                    raise CredentialIssuanceError(
                        f"{account.key} is not seeded as {account.role}; run 'seed' first."
                    )
                if not user.is_active:
                    raise CredentialIssuanceError(f"{account.key} is disabled.")
                if user.has_usable_password() and not reissue:
                    skipped += 1
                    continue
                if user.email_verified_at is None:
                    raise CredentialIssuanceError(
                        f"{account.key} has no verified email; it is not a credential account."
                    )
                replacing = user.has_usable_password()
                credential = _generate(user)
                user.set_password(credential)
                user.save(update_fields=["password", "updated_at"])
                if replacing:
                    invalidate_reusable_auth_state(
                        user_id=user.pk,
                        context=context,
                        reason="password_changed",
                        email_challenge_purposes=(
                            EmailOTPPurpose.RECOVERY,
                            EmailOTPPurpose.EMAIL_VERIFICATION,
                        ),
                        email_challenge_email=user.email,
                    )
                record_event(
                    context=context,
                    action=AUTH_PASSWORD_RESET if replacing else AUTH_PASSWORD_INITIAL_SET,
                    outcome="SUCCESS",
                    target_type="accounts.user",
                    target_id=user.pk,
                    metadata={"method": REISSUE_METHOD if replacing else ISSUANCE_METHOD},
                )
                rows.append(
                    (account.key, account.institutional_id, user.email, account.role, credential)
                )
            if rows:
                _write_handoff(target, rows)
                written = True
    except BaseException:
        # Nothing was committed, so a file written before the failure holds no valid credential.
        if written:
            target.unlink(missing_ok=True)
        raise
    finally:
        reset_current_request_id(token)
    return IssuanceOutcome(issued=len(rows), skipped=skipped, path=target)


def _write_handoff(target: Path, rows: list[tuple[str, ...]]) -> None:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(HANDOFF_COLUMNS)
    writer.writerows(rows)
    # O_EXCL never follows or replaces an existing file; 0600 before any byte is written.
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, buffer.getvalue().encode("utf-8"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


__all__ = [
    "CredentialIssuanceError",
    "HANDOFF_COLUMNS",
    "IssuanceOutcome",
    "issue_credentials",
]
