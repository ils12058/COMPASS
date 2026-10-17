"""Source-owned delivery eligibility. Every transport rechecks before provider handoff."""


def notification_is_current(notification, *, now=None):
    if notification.source_type == "appointment_reminder":
        from compass.appointments.reminders import reminder_notification_is_current

        return reminder_notification_is_current(notification, now=now)
    return notification.recipient.is_active
