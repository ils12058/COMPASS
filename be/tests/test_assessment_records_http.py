"""Six local scenarios through the actual HTTP/session/CSRF boundary and PostgreSQL.

Set COMPASS_ASSESSMENT_BROWSER_E2E=1 with a local Next server at :3107 to additionally run
the real-browser catalog/create/correction path. Its API rewrite must point at :58319.
No live infrastructure or real key is used.
"""

import json
import os
import subprocess
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from compass.accounts.models import User
from compass.assessment_records.models import StudentAssessmentRecord
from compass.audit.models import AuditEvent
from compass.common.institutional_time import institution_today
from tests.test_assessment_records import BASE, PAYLOAD, grant
from tests.test_assessment_records import world as world
from tests.test_notifications import auth_client


class HttpSession:
    def __init__(self, base, actor):
        self.base = base
        self.session = auth_client(actor).cookies["compass_session"].value
        self.csrf = ""
        status, body = self.call("GET", "/api/v1/auth/csrf")
        assert status == 200
        self.csrf = body["csrf_token"]

    def call(self, method, path, body=None):
        headers = {"Cookie": f"compass_session={self.session}; compass_csrf={self.csrf}"}
        if body is not None:
            headers.update({"Content-Type": "application/json", "X-CSRFToken": self.csrf})
        request = Request(
            self.base + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
            method=method,
        )
        try:
            response = urlopen(request, timeout=20)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())


@pytest.mark.django_db(transaction=True)
def test_six_local_http_scenarios(world, live_server, settings):
    settings.CSRF_TRUSTED_ORIGINS = ["http://localhost:3107", "http://127.0.0.1:3107"]
    head = HttpSession(live_server.url, world.head)
    # A: catalog creation and historical use of a deactivated type.
    status, catalog_type = head.call(
        "POST", BASE + "/types", {"name": "Local Career Aptitude Test"}
    )
    assert status == 201 and catalog_type["is_active"]
    # B: persisted confidential fields, structural list and explicitly decrypted detail.
    payload = {
        "student_id": str(world.student.pk),
        "assessment_type_id": catalog_type["id"],
        "administered_on": institution_today().isoformat(),
        **PAYLOAD,
    }
    status, created = head.call("POST", BASE, payload)
    assert status == 201
    record_path = BASE + "/" + created["id"]
    assert {key: created[key] for key in PAYLOAD} == PAYLOAD
    status, listed = head.call("GET", BASE)
    assert status == 200 and listed["items"][0]["id"] == created["id"]
    assert not set(PAYLOAD).intersection(listed["items"][0])
    raw = StudentAssessmentRecord.objects.get(pk=created["id"])
    assert all(value not in raw.confidential_content_ciphertext for value in PAYLOAD.values())
    status, inactive = head.call(
        "PATCH", BASE + "/types/" + catalog_type["id"], {"is_active": False}
    )
    assert status == 200 and not inactive["is_active"]
    assert head.call("GET", record_path)[0] == 200
    assert head.call("POST", BASE, payload)[0] == 422
    assert head.call("PATCH", BASE + "/types/" + catalog_type["id"], {"is_active": True})[0] == 200
    # C: correction persists, auditing remains content-free.
    corrected = {"score": "HTTP_CORRECTED_SCORE", "result": "HTTP_CORRECTED_RESULT"}
    status, updated = head.call("PATCH", record_path, corrected)
    assert status == 200 and all(updated[key] == value for key, value in corrected.items())
    audit = AuditEvent.objects.filter(action="assessment_record.updated").latest("occurred_at")
    assert not any(value in json.dumps(audit.metadata) for value in corrected.values())
    # E: Head is explicit institution-wide; ordinary access is bounded after override.
    other = {
        **payload,
        "student_id": str(world.other_student.pk),
        "assessment_type_id": str(world.assessment_type.pk),
    }
    status, second = head.call("POST", BASE, other)
    assert status == 201
    ordinary = HttpSession(live_server.url, world.ordinary)
    assert ordinary.call("GET", BASE)[0] == 403
    grant(world.ordinary)
    assert ordinary.call("GET", record_path)[0] == 200
    assert ordinary.call("GET", BASE + "/" + second["id"])[0] == 404
    assert len(head.call("GET", BASE)[1]["items"]) == 2
    # D: copying an otherwise valid envelope across Student/record/type fails closed.
    target = StudentAssessmentRecord.objects.get(pk=second["id"])
    StudentAssessmentRecord.objects.filter(pk=target.pk).update(
        confidential_content_ciphertext=raw.confidential_content_ciphertext
    )
    status, refused = head.call("GET", BASE + "/" + second["id"])
    assert status == 500
    assert refused["error"]["code"] == "assessment_record_content_unavailable"
    assert not any(value in json.dumps(refused) for value in PAYLOAD.values())
    # F: historical reads survive lifecycle changes; creation selection remains current-only.
    User.objects.filter(pk=world.student.pk).update(student_lifecycle_status="GRADUATED")
    assert head.call("GET", record_path)[0] == 200
    picker = head.call("GET", BASE + "/students")[1]
    assert str(world.student.pk) not in {item["id"] for item in picker["items"]}
    assert head.call("POST", BASE, payload)[0] == 404

    if os.environ.get("COMPASS_ASSESSMENT_BROWSER_E2E") == "1":
        # Restore one synthetic eligible target for the browser; the real API authorizes each call.
        User.objects.filter(pk=world.student.pk).update(student_lifecycle_status="CURRENT")
        frontend = Path(__file__).resolve().parents[2] / "fe"
        data = {
            "session": head.session,
            "studentName": world.student.get_full_name(),
            "today": institution_today().isoformat(),
        }
        completed = subprocess.run(
            ["node", "tests/assessment-records.live.mjs"],
            cwd=frontend,
            input=json.dumps(data),
            text=True,
            capture_output=True,
            timeout=180,
            env={**os.environ, "COMPASS_UI_BASE_URL": "http://localhost:3107"},
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        browser_record = StudentAssessmentRecord.objects.get(
            confidential_content_ciphertext__isnull=False,
            assessment_type__name="Browser Career Aptitude Test",
        )
        assert all(
            value not in browser_record.confidential_content_ciphertext
            for value in ("BROWSER-SCORE", "BROWSER-RESULT", "BROWSER-CORRECTED")
        )
        assert "BROWSER-CORRECTED" not in json.dumps(
            list(AuditEvent.objects.values_list("metadata", flat=True))
        )
