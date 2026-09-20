"""Authenticated self-service API for the current COMPASS account profile."""

from __future__ import annotations

from datetime import date, datetime
from typing import NoReturn
from uuid import UUID

from ninja import File, Router, Schema, UploadedFile
from pydantic import ConfigDict

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError

from .profile_photos import (
    ProfilePhotoValidationError,
    profile_photo_url,
    remove_profile_photo,
    set_profile_photo,
)
from .profiles import (
    InvalidProfileInput,
    ProfileError,
    ProfileUnavailable,
    update_my_profile,
)

router = Router(tags=["profile"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class MyProfileResponse(StrictSchema):
    user_id: UUID
    institutional_id: str | None
    email: str
    first_name: str
    middle_name: str
    last_name: str
    suffix: str
    full_name: str
    role: str
    date_of_birth: date | None
    civil_status: str
    contact_number: str
    current_address: str
    permanent_address: str
    profile_photo_url: str | None
    profile_photo_updated_at: datetime | None


class MyProfileUpdateRequest(StrictSchema):
    date_of_birth: date | None = None
    civil_status: str = ""
    contact_number: str = ""
    current_address: str = ""
    permanent_address: str = ""


class MyProfilePhotoResponse(StrictSchema):
    profile_photo_url: str | None
    profile_photo_updated_at: datetime | None


def _serialize(user) -> dict[str, object]:
    return {
        "user_id": user.pk,
        "institutional_id": user.institutional_id,
        "email": user.email,
        "first_name": user.first_name,
        "middle_name": user.middle_name,
        "last_name": user.last_name,
        "suffix": user.suffix,
        "full_name": user.get_full_name(),
        "role": user.role.code,
        "date_of_birth": user.date_of_birth,
        "civil_status": user.civil_status,
        "contact_number": user.contact_number,
        "current_address": user.current_address,
        "permanent_address": user.permanent_address,
        "profile_photo_url": profile_photo_url(user),
        "profile_photo_updated_at": user.profile_photo_updated_at,
    }


def _raise_profile_error(exc: ProfileError) -> NoReturn:
    if isinstance(exc, InvalidProfileInput):
        raise APIError(422, "invalid_profile_request", str(exc)) from exc
    if isinstance(exc, ProfileUnavailable):
        raise APIError(403, "profile_unavailable", "The account profile is unavailable.") from exc
    raise APIError(500, "internal_error", "The profile operation could not be completed.") from exc


@router.get(
    "/profile",
    response=response_with_errors(MyProfileResponse, 401, 403),
    auth=session_auth,
    operation_id="profileGetMyProfile",
    summary="View my profile",
)
def get_my_profile(request):
    if not request.auth_user.is_active:
        raise APIError(403, "profile_unavailable", "The account profile is unavailable.")
    return _serialize(request.auth_user)


@router.patch(
    "/profile",
    response=response_with_errors(MyProfileResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="profileUpdateMyProfile",
    summary="Update my profile",
)
def patch_my_profile(request, payload: MyProfileUpdateRequest):
    changes = payload.model_dump(exclude_unset=True)
    try:
        result = update_my_profile(
            user=request.auth_user,
            changes=changes,
            context=AuditContext.from_request(request, actor=request.auth_user),
        )
    except ProfileError as exc:
        _raise_profile_error(exc)
    return _serialize(result.user)


@router.put(
    "/me/profile/photo",
    response=response_with_errors(MyProfilePhotoResponse, 401, 403, 422, 503),
    auth=session_auth,
    operation_id="profileSetMyPhoto",
    summary="Set my profile photo",
)
def set_my_profile_photo(request, photo: UploadedFile = File(...)):  # noqa: B008
    user = request.auth_user
    if not user.is_active:
        raise APIError(403, "profile_unavailable", "The account profile is unavailable.")
    try:
        set_profile_photo(user, photo)
        url = profile_photo_url(user)
    except ProfilePhotoValidationError as exc:
        raise APIError(422, "invalid_profile_photo", str(exc)) from exc
    except Exception as exc:
        raise APIError(
            503,
            "profile_photo_storage_unavailable",
            "Profile photo storage is temporarily unavailable.",
        ) from exc
    return {
        "profile_photo_url": url,
        "profile_photo_updated_at": user.profile_photo_updated_at,
    }


@router.delete(
    "/me/profile/photo",
    response=response_with_errors(MyProfilePhotoResponse, 401, 403, 503),
    auth=session_auth,
    operation_id="profileRemoveMyPhoto",
    summary="Remove my profile photo",
)
def remove_my_profile_photo(request):
    user = request.auth_user
    if not user.is_active:
        raise APIError(403, "profile_unavailable", "The account profile is unavailable.")
    try:
        remove_profile_photo(user)
        url = profile_photo_url(user)
    except Exception as exc:
        raise APIError(
            503,
            "profile_photo_storage_unavailable",
            "Profile photo storage is temporarily unavailable.",
        ) from exc
    return {
        "profile_photo_url": url,
        "profile_photo_updated_at": user.profile_photo_updated_at,
    }
