"""Authorized structural selection and atomic encrypted record corrections."""

import unicodedata
from dataclasses import asdict
from datetime import date
from enum import StrEnum

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models.functions import Lower

from compass.accounts.models import StudentLifecycleStatus, User
from compass.audit import actions
from compass.audit.context import AuditContext
from compass.audit.services import record_event
from compass.common.institutional_time import institution_today
from compass.common.ordering import parse_ordering
from compass.operational_students import list_scoped_operational_students
from compass.organization.access_scope import (
    is_head_guidance,
    resolve_operational_responsibility_scope,
)

from .confidential_content import (
    CONTENT_LIMITS,
    project_confidential_input,
    read_confidential_content,
    validate_text,
    write_confidential_content,
)
from .errors import (
    AssessmentRecordAccessDenied,
    AssessmentRecordConflict,
    AssessmentRecordNotFound,
    InvalidAssessmentRecordInput,
)
from .models import AssessmentType, StudentAssessmentRecord


class AssessmentRecordOrdering(StrEnum):
    NEWEST_ADMINISTERED = "NEWEST_ADMINISTERED"
    OLDEST_ADMINISTERED = "OLDEST_ADMINISTERED"
    RECENTLY_UPDATED = "RECENTLY_UPDATED"
    STUDENT_ASC = "STUDENT_ASC"
    STUDENT_DESC = "STUDENT_DESC"


ORDER_BY = {
    AssessmentRecordOrdering.NEWEST_ADMINISTERED: ("-administered_on", "id"),
    AssessmentRecordOrdering.OLDEST_ADMINISTERED: ("administered_on", "id"),
    AssessmentRecordOrdering.RECENTLY_UPDATED: ("-updated_at", "id"),
    AssessmentRecordOrdering.STUDENT_ASC: (
        Lower("student__last_name"),
        Lower("student__first_name"),
        "id",
    ),
    AssessmentRecordOrdering.STUDENT_DESC: (
        Lower("student__last_name").desc(),
        Lower("student__first_name").desc(),
        "id",
    ),
}


def require_actor(actor, capability="assessment_records.view", *, catalog=False):
    actor = User.objects.select_related("role").filter(pk=getattr(actor, "pk", None)).first()
    if (
        actor is None
        or not actor.is_active
        or actor.role.code != "COUNSELOR"
        or not actor.has_capability(capability)
        or (catalog and not is_head_guidance(actor))
    ):
        raise AssessmentRecordAccessDenied("Assessment Records access is required.")
    return actor


def _scope(actor):
    return (
        None
        if is_head_guidance(actor)
        else resolve_operational_responsibility_scope(actor).college_ids
    )


def _students(actor):
    qs = User.objects.filter(role__code="STUDENT")
    colleges = _scope(actor)
    if colleges is not None:
        qs = qs.filter(
            organization_student_affiliation__college_id__in=colleges,
            organization_student_affiliation__college__is_active=True,
            organization_student_affiliation__college__campus__is_active=True,
        )
    return qs


def _records(actor):
    return StudentAssessmentRecord.objects.filter(student_id__in=_students(actor).values("pk"))


def eligible_students(*, actor, **query):
    actor = require_actor(actor, "assessment_records.manage")
    return list_scoped_operational_students(college_ids=_scope(actor), **query)


def _page(qs, page, page_size):
    if type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 50:
        raise InvalidAssessmentRecordInput("page/page_size are invalid.")
    offset = (page - 1) * page_size
    rows = list(qs[offset : offset + page_size + 1])
    return {
        "items": rows[:page_size],
        "page": page,
        "page_size": page_size,
        "has_next": len(rows) > page_size,
    }


def list_types(*, actor, active_only=False):
    require_actor(actor)
    qs = AssessmentType.objects.order_by(Lower("name"), "id")
    if active_only:
        qs = qs.filter(is_active=True)
    return list(qs)


def _type_values(values):
    normalized = dict(values)
    if "name" in normalized:
        name = validate_text(normalized["name"], "name", 160)
        if any(unicodedata.category(char) in {"Cc", "Cs"} for char in name):
            raise InvalidAssessmentRecordInput("name contains an unsupported character.")
        normalized["name"] = " ".join(name.split())
        if not normalized["name"]:
            raise InvalidAssessmentRecordInput("name is required.")
    if "description" in normalized:
        validate_text(normalized["description"], "description", 2000)
    if "is_active" in normalized and type(normalized["is_active"]) is not bool:
        raise InvalidAssessmentRecordInput("is_active must be a boolean.")
    return normalized


def _audit(actor, context, action, item, *, record=False):
    record_event(
        context=context or AuditContext.user(actor),
        action=action,
        outcome="SUCCESS",
        target_type="assessment.record" if record else "assessment.type",
        target_id=item.pk,
        metadata={"assessment_type_id": str(item.assessment_type_id)} if record else {},
    )


def create_type(*, actor, values, context=None):
    actor = require_actor(actor, "assessment_records.manage", catalog=True)
    values = _type_values(values)
    try:
        with transaction.atomic():
            item = AssessmentType.objects.create(**values)
            _audit(actor, context, actions.ASSESSMENT_TYPE_CREATED, item)
    except IntegrityError:
        raise AssessmentRecordConflict(
            "An Assessment Type with this name already exists."
        ) from None
    return item


def update_type(*, actor, type_id, values, context=None):
    actor = require_actor(actor, "assessment_records.manage", catalog=True)
    values = _type_values(values)
    try:
        with transaction.atomic():
            item = AssessmentType.objects.select_for_update(of=("self",)).filter(pk=type_id).first()
            if item is None:
                raise AssessmentRecordNotFound("The Assessment Type was not found.")
            changed = {key: value for key, value in values.items() if getattr(item, key) != value}
            if not changed:
                return item
            active_before = item.is_active
            for key, value in changed.items():
                setattr(item, key, value)
            item.save(update_fields=[*changed, "updated_at"])
            _audit(actor, context, actions.ASSESSMENT_TYPE_UPDATED, item)
            if active_before != item.is_active:
                action = (
                    actions.ASSESSMENT_TYPE_REACTIVATED
                    if item.is_active
                    else actions.ASSESSMENT_TYPE_DEACTIVATED
                )
                _audit(actor, context, action, item)
    except IntegrityError:
        raise AssessmentRecordConflict(
            "An Assessment Type with this name already exists."
        ) from None
    return item


def list_records(
    *,
    actor,
    search=None,
    student_id=None,
    assessment_type_id=None,
    administered_from=None,
    administered_to=None,
    page=1,
    page_size=20,
    ordering=AssessmentRecordOrdering.NEWEST_ADMINISTERED,
):
    actor = require_actor(actor)
    ordering = parse_ordering(
        ordering,
        AssessmentRecordOrdering,
        default=AssessmentRecordOrdering.NEWEST_ADMINISTERED,
        error=InvalidAssessmentRecordInput,
    )
    if administered_from and administered_to and administered_from > administered_to:
        raise InvalidAssessmentRecordInput("The From date must not follow the To date.")
    qs = _records(actor)
    if student_id is not None:
        qs = qs.filter(student_id=student_id)
    if assessment_type_id is not None:
        qs = qs.filter(assessment_type_id=assessment_type_id)
    if administered_from is not None:
        qs = qs.filter(administered_on__gte=administered_from)
    if administered_to is not None:
        qs = qs.filter(administered_on__lte=administered_to)
    if search:
        term = validate_text(search, "search", 160).strip()
        qs = qs.filter(
            Q(student__institutional_id__icontains=term)
            | Q(student__first_name__icontains=term)
            | Q(student__middle_name__icontains=term)
            | Q(student__last_name__icontains=term)
            | Q(assessment_type__name__icontains=term)
        )
    # No result column or private account profile is selected on this structural path.
    qs = qs.select_related("student", "recorded_by", "assessment_type").only(
        "id",
        "student_id",
        "assessment_type_id",
        "administered_on",
        "recorded_by_id",
        "created_at",
        "updated_at",
        "student__id",
        "student__institutional_id",
        "student__first_name",
        "student__middle_name",
        "student__last_name",
        "recorded_by__id",
        "recorded_by__institutional_id",
        "recorded_by__first_name",
        "recorded_by__middle_name",
        "recorded_by__last_name",
        "assessment_type__id",
        "assessment_type__name",
        "assessment_type__description",
        "assessment_type__is_active",
        "assessment_type__created_at",
        "assessment_type__updated_at",
    )
    return {**_page(qs.order_by(*ORDER_BY[ordering]), page, page_size), "ordering": ordering}


def get_record(*, actor, record_id):
    actor = require_actor(actor)
    item = (
        _records(actor)
        .select_related("student", "recorded_by", "assessment_type")
        .filter(pk=record_id)
        .first()
    )
    if item is None:
        raise AssessmentRecordNotFound("The Assessment Record was not found.")
    return item, read_confidential_content(item)


def _date(value):
    if type(value) is not date or value > institution_today():
        raise InvalidAssessmentRecordInput(
            "administered_on must be a calendar date that is not in the future."
        )
    return value


def _active_type(type_id):
    item = AssessmentType.objects.select_for_update(of=("self",)).filter(pk=type_id).first()
    if item is None or not item.is_active:
        raise InvalidAssessmentRecordInput("Choose an active Assessment Type.")
    return item


def create_record(*, actor, values, context=None):
    actor = require_actor(actor, "assessment_records.manage")
    content = project_confidential_input({key: values.get(key, "") for key in CONTENT_LIMITS})
    administered = _date(values["administered_on"])
    with transaction.atomic():
        student = (
            _students(actor)
            .select_for_update(of=("self",))
            .filter(
                pk=values["student_id"],
                is_active=True,
                student_lifecycle_status=StudentLifecycleStatus.CURRENT,
            )
            .first()
        )
        if student is None:
            raise AssessmentRecordNotFound("The Student was not found.")
        item = StudentAssessmentRecord(
            student=student,
            assessment_type=_active_type(values["assessment_type_id"]),
            administered_on=administered,
            recorded_by=actor,
        )
        write_confidential_content(item, content)
        item.save()
        _audit(actor, context, actions.ASSESSMENT_RECORD_CREATED, item, record=True)
    return item, content


def update_record(*, actor, record_id, values, context=None):
    actor = require_actor(actor, "assessment_records.manage")
    if set(values) - {*CONTENT_LIMITS, "assessment_type_id", "administered_on"}:
        raise InvalidAssessmentRecordInput("Only the allowed correction fields may change.")
    with transaction.atomic():
        item = _records(actor).select_for_update(of=("self",)).filter(pk=record_id).first()
        if item is None:
            raise AssessmentRecordNotFound("The Assessment Record was not found.")
        previous = read_confidential_content(item)
        content = project_confidential_input(
            {**asdict(previous), **{k: v for k, v in values.items() if k in CONTENT_LIMITS}}
        )
        type_changed = (
            "assessment_type_id" in values
            and values["assessment_type_id"] != item.assessment_type_id
        )
        if type_changed:
            item.assessment_type = _active_type(values["assessment_type_id"])
        date_changed = (
            "administered_on" in values and _date(values["administered_on"]) != item.administered_on
        )
        if not type_changed and not date_changed and content == previous:
            return item, previous
        if "administered_on" in values:
            item.administered_on = _date(values["administered_on"])
        write_confidential_content(item, content)
        item.save(
            update_fields=[
                "assessment_type",
                "administered_on",
                "confidential_content_ciphertext",
                "updated_at",
            ]
        )
        _audit(actor, context, actions.ASSESSMENT_RECORD_UPDATED, item, record=True)
    return item, content
