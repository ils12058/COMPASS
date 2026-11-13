"""Review all pending work; apply only explicitly authorized task changes at acceptance."""

import hashlib

from django.utils import timezone

from compass.guidance_followups import policy as task_policy
from compass.guidance_followups.content import decrypt_text, encrypt_text
from compass.guidance_followups.models import GuidanceFollowUp
from compass.guidance_followups.services import _audit as task_audit
from compass.guidance_followups.services import _event as task_event

from .case_continuity_rules import fail, locked_rows
from .case_models import CounselingCaseAppointment
from .case_transfer_models import (
    CaseAppointmentDisposition,
    CaseAppointmentRetentionReason,
    CaseTaskDisposition,
    CounselingCaseTransferAppointment,
    CounselingCaseTransferTask,
)


def case_tasks(case):
    return GuidanceFollowUp.objects.filter(case_id=case.pk).select_related(
        "student__role", "assigned_to__role"
    )


def upcoming_links(case, now):
    return CounselingCaseAppointment.objects.filter(
        case_id=case.pk,
        removed_at__isnull=True,
        appointment__status="SCHEDULED",
        appointment__starts_at__gt=now,
    ).select_related("appointment__provider", "appointment__service")


def disposition_allowed(task, *, office, reason, actor):
    if task.source_kind is None and task.source_id is None:
        return (CaseTaskDisposition.TRANSFER, CaseTaskDisposition.RESOLVE_FIRST)
    if office:
        return (CaseTaskDisposition.RESOLVE_FIRST,)
    choices = [CaseTaskDisposition.RESOLVE_FIRST]
    if reason != "IMPARTIALITY_CONCERN":
        choices.append(CaseTaskDisposition.RETAIN)
    if task_policy.authorized(actor, task, manage=True):
        choices.append(CaseTaskDisposition.HAND_OVER_AS_NEW)
    return tuple(choices)


def store_plans(transfer, *, actor, tasks, appointments, now):
    office = transfer.prepared_by_id != transfer.outgoing_counselor_id
    pending = {task.pk: task for task in case_tasks(transfer.case).filter(status="PENDING")}
    submitted = {item["task_id"]: item for item in tasks}
    if len(submitted) != len(tasks):
        fail("task_plan_invalid", "Review each pending action once.", 422)
    if set(pending) != set(submitted):
        fail("task_plan_incomplete", "Every pending case action needs a disposition.")
    transfer.task_plans.all().delete()
    for task_id, values in submitted.items():
        task = pending[task_id]
        if values["expected_version"] != task.version:
            fail("task_changed", "A case action changed. Review the task plan again.")
        disposition = values["disposition"]
        if disposition not in disposition_allowed(
            task, office=office, reason=transfer.reason, actor=actor
        ):
            fail("task_disposition_forbidden", "This action cannot use that disposition.", 422)
        plan = CounselingCaseTransferTask(
            transfer=transfer,
            task=task,
            disposition=disposition,
            task_version=task.version,
            source_kind=task.source_kind,
            source_id=task.source_id,
            assignee_id=task.assigned_to_id,
            due_at=task.due_at,
        )
        title, due = values.get("successor_title"), values.get("successor_due_at")
        if disposition == CaseTaskDisposition.HAND_OVER_AS_NEW:
            if not title or due is None or timezone.is_naive(due) or due <= now:
                fail(
                    "successor_required",
                    "Give the new case action a title and a future due date.",
                    422,
                )
            plan.successor_title_ciphertext = encrypt_text(plan.pk, "title", title, required=True)
            plan.successor_due_at = due
        elif title is not None or due is not None:
            fail(
                "task_plan_invalid",
                "Only a new successor action may have a new title or deadline.",
                422,
            )
        plan.save(force_insert=True)

    links = {link.pk: link for link in upcoming_links(transfer.case, now)}
    submitted_appointments = {item["link_id"]: item for item in appointments}
    if len(submitted_appointments) != len(appointments) or set(links) != set(
        submitted_appointments
    ):
        fail("appointment_plan_incomplete", "Every upcoming linked Appointment needs a plan.")
    transfer.appointment_plans.all().delete()
    for link_id, values in submitted_appointments.items():
        link = links[link_id]
        disposition = values["disposition"]
        retention = values.get("retention_reason") or ""
        if disposition not in CaseAppointmentDisposition.values:
            fail("appointment_plan_invalid", "Choose an Appointment plan.", 422)
        if disposition == CaseAppointmentDisposition.RETAIN_WITH_PROVIDER:
            if retention not in CaseAppointmentRetentionReason.values:
                fail(
                    "retention_reason_required",
                    "Record why the Appointment retains its provider.",
                    422,
                )
            if (
                transfer.reason == "IMPARTIALITY_CONCERN"
                and link.appointment.provider_id == transfer.outgoing_counselor_id
            ):
                fail(
                    "conflicted_provider",
                    "An impartiality-related transfer cannot retain "
                    "the outgoing Counselor as provider.",
                    422,
                )
        elif retention:
            fail(
                "appointment_plan_invalid",
                "A retention reason belongs only to retaining the provider.",
                422,
            )
        CounselingCaseTransferAppointment.objects.create(
            transfer=transfer,
            link=link,
            disposition=disposition,
            retention_reason=retention,
            provider_id=link.appointment.provider_id,
            starts_at=link.appointment.starts_at,
            ends_at=link.appointment.ends_at,
        )


def validate_plans(transfer, *, actor, now, accepting=False):
    tasks = {row.pk: row for row in locked_rows(case_tasks(transfer.case))}
    plans = tuple(transfer.task_plans.select_related("assignee__role", "task__student__role"))
    covered = {plan.task_id for plan in plans}
    if any(task.status == "PENDING" and task.pk not in covered for task in tasks.values()):
        fail("task_plan_incomplete", "A pending action has no reviewed disposition.")
    office = transfer.prepared_by_id != transfer.outgoing_counselor_id
    for plan in plans:
        task = tasks.get(plan.task_id)
        if (
            task is None
            or task.student_id != transfer.case.student_id
            or task.source_kind != plan.source_kind
            or task.source_id != plan.source_id
            or task.assigned_to_id != plan.assignee_id
            or task.due_at != plan.due_at
        ):
            fail("task_changed", "A case action changed. Prepare a fresh review.")
        if plan.disposition == CaseTaskDisposition.RESOLVE_FIRST:
            if accepting and task.status == "PENDING":
                fail(
                    "task_resolution_required",
                    "Complete or cancel every action marked Resolve first through Follow-ups.",
                )
            if task.status == "PENDING" and task.version != plan.task_version:
                fail("task_changed", "A case action changed. Prepare a fresh review.")
            continue
        if task.status != "PENDING" or task.version != plan.task_version:
            fail("task_changed", "A planned action changed. Prepare a fresh review.")
        if plan.disposition not in disposition_allowed(
            task, office=office, reason=transfer.reason, actor=actor
        ):
            fail("task_disposition_forbidden", "A task disposition is no longer available.")
        if plan.disposition in {CaseTaskDisposition.RETAIN, CaseTaskDisposition.HAND_OVER_AS_NEW}:
            if not plan.assignee.is_active or not plan.assignee.has_capability(
                "guidance_followups.manage", at=now
            ):
                fail(
                    "task_assignee_ineligible",
                    "An action's current assignee is no longer eligible.",
                )
            try:
                task_policy.require_source(
                    plan.assignee,
                    kind=task.source_kind,
                    source_id=task.source_id,
                    student_id=task.student_id,
                    manage=True,
                )
            except task_policy.FollowUpNotFound:
                fail(
                    "task_source_changed",
                    "An action's source authority changed. Prepare a fresh review.",
                )
        if (
            plan.disposition == CaseTaskDisposition.HAND_OVER_AS_NEW
            and plan.successor_due_at <= now
        ):
            fail("successor_due_expired", "The successor deadline passed. Prepare a fresh review.")

    appointment_plans = tuple(
        transfer.appointment_plans.select_related("link__appointment__service")
    )
    linked_ids = {link.pk for link in upcoming_links(transfer.case, now)}
    if linked_ids - {plan.link_id for plan in appointment_plans}:
        fail("appointment_plan_incomplete", "An upcoming linked Appointment has no reviewed plan.")
    for plan in appointment_plans:
        link, appointment = plan.link, plan.link.appointment
        if (
            link.removed_at
            or link.case_id != transfer.case_id
            or appointment.student_id != transfer.case.student_id
        ):
            fail("appointment_changed", "An Appointment link changed. Prepare a fresh review.")
        if plan.disposition == CaseAppointmentDisposition.CANCEL:
            if accepting and appointment.status != "CANCELLED":
                fail(
                    "appointment_action_required",
                    "Cancel the reviewed Appointment through Appointments before acceptance.",
                )
        elif plan.disposition == CaseAppointmentDisposition.REASSIGN:
            if accepting and appointment.provider_id != transfer.receiving_counselor_id:
                fail(
                    "appointment_action_required",
                    "Reassign the reviewed Appointment through Appointments before acceptance.",
                )
            if (
                appointment.status != "SCHEDULED"
                or appointment.starts_at != plan.starts_at
                or appointment.ends_at != plan.ends_at
            ):
                fail("appointment_changed", "The reviewed Appointment time or status changed.")
        elif plan.disposition == CaseAppointmentDisposition.RESCHEDULE:
            if accepting and appointment.starts_at == plan.starts_at:
                fail(
                    "appointment_action_required",
                    "Reschedule the reviewed Appointment through Appointments before acceptance.",
                )
            if appointment.status != "SCHEDULED":
                fail("appointment_changed", "The reviewed Appointment status changed.")
            if (
                accepting
                and transfer.reason == "IMPARTIALITY_CONCERN"
                and appointment.provider_id == transfer.outgoing_counselor_id
            ):
                fail(
                    "conflicted_provider",
                    "Review a plan that does not retain the outgoing Counselor as provider.",
                )
        else:
            if (
                appointment.status != "SCHEDULED"
                or appointment.provider_id != plan.provider_id
                or appointment.starts_at != plan.starts_at
                or appointment.ends_at != plan.ends_at
            ):
                fail(
                    "appointment_changed", "A retained Appointment changed. Prepare a fresh review."
                )
            if (
                transfer.reason == "IMPARTIALITY_CONCERN"
                and appointment.provider_id == transfer.outgoing_counselor_id
            ):
                fail(
                    "conflicted_provider",
                    "An impartiality-related transfer cannot retain "
                    "the outgoing Counselor as provider.",
                )
    return plans, tasks


def new_case_task(*, case, author, assignee, title, due_at, identity, predecessor=None, context):
    # The continuity boundary has already authorized the package. This deliberately does not
    # impersonate the historical source author or borrow the ordinary source-task creation ACL.
    digest = hashlib.sha256(identity.encode()).hexdigest()
    task = GuidanceFollowUp(
        student_id=case.student_id,
        case=case,
        assigned_to=assignee,
        created_by=author,
        category="COUNSELING",
        visibility="COUNSELOR_CONFIDENTIAL",
        due_at=due_at,
        predecessor=predecessor,
        creation_key_digest=digest,
        creation_request_fingerprint=digest,
    )
    task.title_ciphertext = encrypt_text(task.pk, "title", title, required=True)
    task.save(force_insert=True)
    task_event(task, actor=author, kind="CREATED", new_assignee=assignee, new_due=due_at)
    task_audit(context, "created", task, metadata={"category": "COUNSELING"})
    return task


def apply_task_plans(transfer, plans, tasks, *, receiver, requester, context, now):
    for plan in plans:
        task = tasks[plan.task_id]
        if plan.disposition == CaseTaskDisposition.TRANSFER:
            old_assignee = task.assigned_to
            task.assigned_to = receiver
            task.version += 1
            task.save(update_fields=["assigned_to", "version", "updated_at"])
            event = task_event(
                task,
                actor=receiver,
                kind="REASSIGNED",
                old_assignee=old_assignee,
                new_assignee=receiver,
            )
            event.case_transfer = transfer
            event.save(update_fields=["case_transfer"])
            task_audit(context, "reassigned", task, metadata={"case_transfer_id": str(transfer.pk)})
        elif plan.disposition == CaseTaskDisposition.HAND_OVER_AS_NEW:
            title = decrypt_text(plan.pk, "title", plan.successor_title_ciphertext)
            plan.successor = new_case_task(
                case=transfer.case,
                author=requester,
                assignee=receiver,
                title=title,
                due_at=plan.successor_due_at,
                predecessor=task,
                identity=f"case-transfer:{transfer.pk}:{task.pk}",
                context=context,
            )
            plan.save(update_fields=["successor"])
            task.status = "CANCELLED"
            task.cancelled_at, task.cancelled_by = now, receiver
            task.version += 1
            task.save(
                update_fields=["status", "cancelled_at", "cancelled_by", "version", "updated_at"]
            )
            event = task_event(
                task,
                actor=receiver,
                kind="CANCELLED",
                remarks="Handed over as a new case action through an accepted case transfer.",
            )
            event.case_transfer = transfer
            event.save(update_fields=["case_transfer"])
            task_audit(context, "cancelled", task, metadata={"case_transfer_id": str(transfer.pk)})
