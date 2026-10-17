"""Periodic discovery of due Student Appointment reminders."""

from celery import shared_task

from compass.tasks import CorrelationTask

from .reminders import dispatch_due_reminders


@shared_task(bind=True, base=CorrelationTask, name="compass.appointments.reminders.dispatch_due")
def dispatch_due_appointment_reminders(self) -> int:
    return dispatch_due_reminders()
