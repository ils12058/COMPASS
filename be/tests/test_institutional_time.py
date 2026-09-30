from datetime import datetime, timezone as datetime_timezone
from zoneinfo import ZoneInfo

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from compass.common.institutional_time import (
    institution_timezone_name,
    institution_today,
    institution_zone,
    to_institution_time,
)


@override_settings(TIME_ZONE="UTC", INSTITUTION_TIME_ZONE="Asia/Manila")
def test_institution_timezone_is_independent_from_runtime_timezone():
    assert settings.TIME_ZONE == "UTC"
    assert institution_timezone_name() == "Asia/Manila"
    assert institution_zone().key == "Asia/Manila"


@override_settings(TIME_ZONE="UTC", INSTITUTION_TIME_ZONE="Asia/Manila")
def test_aware_instant_converts_to_institution_time():
    instant = datetime(2026, 10, 2, 14, 0, tzinfo=datetime_timezone.utc)

    converted = to_institution_time(instant)

    assert converted == datetime(2026, 10, 2, 22, 0, tzinfo=ZoneInfo("Asia/Manila"))


@override_settings(TIME_ZONE="UTC", INSTITUTION_TIME_ZONE="Asia/Manila")
def test_institution_today_uses_institutional_calendar_boundary():
    instant = datetime(2026, 9, 30, 17, 0, tzinfo=datetime_timezone.utc)

    assert institution_today(instant).isoformat() == "2026-10-01"


@override_settings(INSTITUTION_TIME_ZONE="Not/A_Real_Zone")
def test_invalid_institution_timezone_fails_explicitly():
    with pytest.raises(ImproperlyConfigured, match="valid IANA timezone"):
        institution_zone()


@override_settings(INSTITUTION_TIME_ZONE="Asia/Manila")
def test_naive_datetime_is_not_silently_interpreted():
    with pytest.raises(ValueError, match="timezone-aware"):
        to_institution_time(datetime(2026, 10, 2, 22, 0))
