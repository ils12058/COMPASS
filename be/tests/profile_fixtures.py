"""Explicit current-profile fixture writes; no audit side effects."""

from dataclasses import asdict

from compass.accounts.confidential_profile import (
    AccountProfileConfidentialContent,
    read_account_profile_confidential_content,
    write_account_profile_confidential_content,
)


def set_profile(user, **changes):
    content = AccountProfileConfidentialContent(
        **{**asdict(read_account_profile_confidential_content(user)), **changes}
    )
    write_account_profile_confidential_content(user, content)
    user.save(update_fields=["profile_confidential_content_ciphertext"])
    return user


def initialized_user(user):
    write_account_profile_confidential_content(user, AccountProfileConfidentialContent())
    return user


def create_initialized_user(**values):
    from compass.accounts.models import User

    user = initialized_user(User(**values))
    user.save(force_insert=True)
    return user
