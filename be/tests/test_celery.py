from django.conf import settings

from compass.notifications.tasks import (
    deliver_notification_email,
    dispatch_due_notification_emails,
)
from compass.tasks import infrastructure_noop
from config.celery import app


def test_celery_is_configured_with_redis_and_diagnostic_task():
    assert app.conf.broker_url.startswith("redis://")
    result = infrastructure_noop.apply()

    assert result.get() == {"status": "ok", "request_id": None}


def test_notification_delivery_tasks_and_beat_recovery_are_registered():
    schedule = settings.CELERY_BEAT_SCHEDULE["notification-email-recovery"]
    assert schedule["task"] == "compass.notifications.email.dispatch_due"
    assert schedule["schedule"] == settings.NOTIFICATION_EMAIL_DISPATCH_INTERVAL_SECONDS
    assert deliver_notification_email.name == "compass.notifications.email.deliver"
    assert dispatch_due_notification_emails.name == "compass.notifications.email.dispatch_due"
