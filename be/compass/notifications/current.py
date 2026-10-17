"""Source-owned eligibility; workers do not need confidential-content keyrings."""

from django.conf import settings


def external_delivery_enabled(notification):
    if notification.source_type == "guidance_followup_event":
        return settings.GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED
    return True


def notification_is_current(notification, *, now=None):
    if not external_delivery_enabled(notification):
        return False
    if notification.source_type == "guidance_followup_event":
        from compass.guidance_followups.integration import followup_notification_is_current

        return followup_notification_is_current(notification)
    return notification.recipient.is_active
