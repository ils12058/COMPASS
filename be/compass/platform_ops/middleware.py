"""Application-level HTTP gate for effective COMPASS Maintenance Mode."""

from __future__ import annotations

import math

from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from compass.common.errors import error_response

from .services import MaintenanceSource, MaintenanceState, get_maintenance_snapshot

_API_PREFIX = "/api/v1/"
_BYPASS_EXACT = frozenset(
    {
        "/api/v1/health/live",
        "/api/v1/health/ready",
        "/api/v1/integrations/daily/webhook",
    }
)
_BYPASS_PREFIXES = (
    "/api/v1/auth/",
    "/api/v1/platform/",
)


def _bypasses_maintenance(path: str) -> bool:
    if path in _BYPASS_EXACT:
        return True
    if path in {"/api/v1/auth", "/api/v1/platform"}:
        return True
    return any(path.startswith(prefix) for prefix in _BYPASS_PREFIXES)


class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        path = request.path
        if not path.startswith(_API_PREFIX) or _bypasses_maintenance(path):
            return self.get_response(request)

        current = timezone.now()
        snapshot = get_maintenance_snapshot(now=current)
        if snapshot.state != MaintenanceState.MAINTENANCE:
            return self.get_response(request)

        details: dict[str, object] = {"source": snapshot.source.value}
        if snapshot.source == MaintenanceSource.SCHEDULED:
            details["scheduled_end_at"] = snapshot.scheduled_end_at.isoformat()
        elif snapshot.manual_expected_end_at is not None:
            details["manual_expected_end_at"] = snapshot.manual_expected_end_at.isoformat()

        response = error_response(
            request,
            status=503,
            code="maintenance_mode",
            message=snapshot.message,
            details=details,
        )
        if (
            snapshot.source == MaintenanceSource.SCHEDULED
            and snapshot.scheduled_end_at is not None
        ):
            remaining = math.ceil((snapshot.scheduled_end_at - current).total_seconds())
            response["Retry-After"] = str(max(1, remaining))
        return response


__all__ = ["MaintenanceModeMiddleware"]
