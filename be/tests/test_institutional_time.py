from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from compass.common.institutional_time import (
    institution_date,
    institution_day_start,
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
    instant = datetime(2026, 10, 2, 14, 0, tzinfo=UTC)

    converted = to_institution_time(instant)

    assert converted == datetime(2026, 10, 2, 22, 0, tzinfo=ZoneInfo("Asia/Manila"))


@override_settings(TIME_ZONE="UTC", INSTITUTION_TIME_ZONE="Asia/Manila")
def test_institution_today_uses_institutional_calendar_boundary():
    instant = datetime(2026, 9, 30, 17, 0, tzinfo=UTC)

    assert institution_today(instant).isoformat() == "2026-10-01"


@override_settings(INSTITUTION_TIME_ZONE="Not/A_Real_Zone")
def test_invalid_institution_timezone_fails_explicitly():
    with pytest.raises(ImproperlyConfigured, match="valid IANA timezone"):
        institution_zone()


@override_settings(INSTITUTION_TIME_ZONE="Asia/Manila")
def test_naive_datetime_is_not_silently_interpreted():
    with pytest.raises(ValueError, match="timezone-aware"):
        to_institution_time(datetime(2026, 10, 2, 22, 0))


@override_settings(TIME_ZONE="UTC", INSTITUTION_TIME_ZONE="Asia/Manila")
@pytest.mark.parametrize(
    ("instant", "expected"),
    [
        # 16:30 UTC is already 00:30 the next day in Manila.
        (datetime(2026, 10, 8, 16, 30, tzinfo=UTC), "2026-10-09"),
        (datetime(2026, 10, 8, 15, 59, tzinfo=UTC), "2026-10-08"),
        # New Year arrives in Manila eight hours before UTC.
        (datetime(2026, 12, 31, 16, 30, tzinfo=UTC), "2027-01-01"),
    ],
)
def test_institution_date_is_the_manila_calendar_day_under_a_utc_runtime(instant, expected):
    assert institution_date(instant).isoformat() == expected
    assert institution_today(instant).isoformat() == expected


@override_settings(TIME_ZONE="UTC", INSTITUTION_TIME_ZONE="Asia/Manila")
def test_institution_day_start_is_manila_midnight_as_an_aware_instant():
    start = institution_day_start(date(2027, 1, 1))

    assert start.utcoffset() is not None
    assert start == datetime(2026, 12, 31, 16, 0, tzinfo=UTC)
    assert institution_date(start).isoformat() == "2027-01-01"
    assert institution_date(start - timedelta(microseconds=1)).isoformat() == "2026-12-31"


@override_settings(INSTITUTION_TIME_ZONE="Asia/Manila")
def test_institution_date_rejects_naive_datetimes():
    with pytest.raises(ValueError, match="timezone-aware"):
        institution_date(datetime(2026, 10, 9, 0, 30))
