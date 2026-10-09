import json
import logging
import sys
import uuid

from compass.common.json_logging import JsonFormatter


def test_valid_request_id_is_reused(client):
    request_id = str(uuid.uuid4())

    response = client.get("/api/v1/health/live", HTTP_X_REQUEST_ID=request_id)

    assert response["X-Request-ID"] == request_id


def test_invalid_request_id_is_replaced(client):
    response = client.get("/api/v1/health/live", HTTP_X_REQUEST_ID="not-a-uuid")

    generated = response["X-Request-ID"]
    assert str(uuid.UUID(generated)) == generated


def _format(**extra) -> dict[str, object]:
    record = logging.LogRecord(
        name="compass.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="synthetic message",
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return json.loads(JsonFormatter().format(record))


def test_json_logs_keep_request_and_task_context_unchanged():
    request_id = str(uuid.uuid4())

    line = _format(
        event="request_completed",
        request_id=request_id,
        method="GET",
        path="/api/v1/health/live",
        status_code=200,
        duration_ms=1.5,
        task_name="compass.tasks.synthetic",
        task_id="task-1",
    )

    assert set(line) == {
        "timestamp",
        "level",
        "logger",
        "event",
        "request_id",
        "method",
        "path",
        "status_code",
        "duration_ms",
        "task_name",
        "task_id",
    }
    assert line["event"] == "request_completed"
    assert line["request_id"] == request_id
    assert line["path"] == "/api/v1/health/live"
    assert line["status_code"] == 200


def test_json_logs_keep_reviewed_diagnostic_fields():
    delivery_id = uuid.uuid4()

    line = _format(
        event="notification_email_delivery_processed",
        email_delivery_id=delivery_id,
        notification_id=str(uuid.uuid4()),
        notification_event_code="appointment.scheduled",
        attempt_number=2,
        delivery_status="FAILED",
        failure_code="smtp_rejected",
        sqlstate="23505",
        exception_class="OSError",
    )

    assert line["email_delivery_id"] == str(delivery_id)
    assert line["notification_event_code"] == "appointment.scheduled"
    assert line["attempt_number"] == 2
    assert line["delivery_status"] == "FAILED"
    assert line["failure_code"] == "smtp_rejected"
    assert line["sqlstate"] == "23505"
    assert line["exception_class"] == "OSError"


def test_json_logs_drop_unknown_and_sensitive_fields():
    line = _format(
        event="synthetic",
        password="correct horse battery staple",
        token="opaque-session-token",
        code="123456",
        recovery_code="ABCD-EFGH",
        storage_key="resources/1/object.pdf",
        url="https://storage.example/object?X-Amz-Signature=secret",
        body="request body",
        metadata={"note": "confidential"},
        error_reason="DocumentRenderError: private detail",
    )

    assert set(line) == {"timestamp", "level", "logger", "event"}


def test_json_logs_drop_unsafe_values_under_reviewed_field_names():
    line = _format(
        event="synthetic",
        reason="Counselor wrote a confidential sentence",
        target_type="https://storage.example/object?X-Amz-Signature=secret",
        failure_code={"raw": "provider response"},
        action=["a", "b"],
        section=object(),
        version="x" * 129,
        delivery_status="",
        sqlstate=None,
    )

    assert set(line) == {"timestamp", "level", "logger", "event"}


def test_json_logs_report_only_the_exception_class():
    try:
        raise ValueError("private exception detail")
    except ValueError:
        record = logging.LogRecord(
            name="compass.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="synthetic failure",
            args=(),
            exc_info=sys.exc_info(),
        )

    line = json.loads(JsonFormatter().format(record))

    assert line["exception_type"] == "ValueError"
    assert "private exception detail" not in json.dumps(line)
