"""Test fixtures mirror the explicit post-migration deployment synchronization."""

import pytest


@pytest.fixture(autouse=True)
def synchronized_institutional_forms(request):
    if request.node.get_closest_marker("django_db") is None and not {
        "db",
        "transactional_db",
    }.intersection(request.fixturenames):
        return
    request.getfixturevalue("_django_db_helper")
    from compass.institutional_forms.bootstrap import sync_institutional_forms

    sync_institutional_forms()
