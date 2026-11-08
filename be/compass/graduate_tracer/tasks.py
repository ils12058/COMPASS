"""Daily Graduate Tracer reminder discovery."""

from celery import shared_task

from compass.tasks import CorrelationTask

from .reminders import dispatch_due_reminders


@shared_task(bind=True, base=CorrelationTask, name="compass.graduate_tracer.reminders.dispatch_due")
def dispatch_due_graduate_tracer_reminders(self) -> int:
    return dispatch_due_reminders()
