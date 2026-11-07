"""Encrypted immutable messages, institutional threads, private read cursors, plain templates."""

import uuid

from django.conf import settings
from django.db import models
from django.db.models.functions import Length, Lower
from django.db.models.lookups import LessThanOrEqual


class ThreadKind(models.TextChoices):
    OFFICE = "OFFICE", "Guidance Office"
    COUNSELING = "COUNSELING", "Counseling"
    FACULTY_INQUIRY = "FACULTY_INQUIRY", "Faculty inquiry"
    REFERRAL_COORDINATION = "REFERRAL_COORDINATION", "Referral coordination"
    COUNSELOR_DIRECT = "COUNSELOR_DIRECT", "Counselor direct"


class ReservedThreadKind(models.TextChoices):
    """Kind codes whose families GMSG-5 will add; only case coordination remains reserved.

    COUNSELOR_CASE_COORDINATION is admitted by the generalized database CHECK, denied for every
    actor by `policy._RULES`, and has no service function and no endpoint. Since 0003 made
    `student` nullable it is no longer blocked by a NOT NULL column, so uncreatability here is a
    policy guarantee only: a direct ORM insert with a satisfiable CHECK branch would store the
    row. The generalized CHECK remains the database-level shape guarantee.
    """

    COUNSELOR_CASE_COORDINATION = "COUNSELOR_CASE_COORDINATION", "Counselor case coordination"


ALL_THREAD_KINDS = frozenset(ThreadKind.values) | frozenset(ReservedThreadKind.values)

# GMSG-0 §6.1 family allowlists: per kind, the columns a row must set and the columns it must leave
# null. A column in neither list is deliberately unconstrained, except for FACULTY_INQUIRY, whose
# branch accounts for every family column. Only these six codes appear here, so a row of any other
# kind matches no branch and is rejected by the CHECK.
_FAMILY_SHAPE: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "OFFICE": (
        ("student", "routing_college"),
        (
            "counselor",
            "relationship_appointment",
            "requester",
            "direct_first_user",
            "direct_second_user",
            "student_subject",
            "relationship_referral",
            "relationship_case_grant",
        ),
    ),
    "COUNSELING": (
        ("student", "counselor", "relationship_appointment"),
        (
            "routing_college",
            "assigned_to",
            "requester",
            "direct_first_user",
            "direct_second_user",
            "student_subject",
            "relationship_referral",
            "relationship_case_grant",
        ),
    ),
    "FACULTY_INQUIRY": (
        ("requester",),
        (
            "student",
            "counselor",
            "relationship_appointment",
            "routing_college",
            "assigned_to",
            "direct_first_user",
            "direct_second_user",
            "student_subject",
            "relationship_referral",
            "relationship_case_grant",
        ),
    ),
    "REFERRAL_COORDINATION": (
        ("requester", "relationship_referral", "student_subject", "routing_college"),
        (
            "student",
            "counselor",
            "relationship_appointment",
            "direct_first_user",
            "direct_second_user",
            "relationship_case_grant",
        ),
    ),
    "COUNSELOR_DIRECT": (
        ("direct_first_user", "direct_second_user"),
        (
            "student",
            "requester",
            "student_subject",
            "relationship_referral",
            "relationship_case_grant",
            "counselor",
            "relationship_appointment",
            "routing_college",
            "assigned_to",
        ),
    ),
    "COUNSELOR_CASE_COORDINATION": (
        ("relationship_case_grant", "student_subject"),
        (
            "student",
            "requester",
            "direct_first_user",
            "direct_second_user",
            "relationship_referral",
            "counselor",
            "relationship_appointment",
            "routing_college",
            "assigned_to",
        ),
    ),
}


def _family_shape_condition():
    branches = []
    for kind, (required, forbidden) in _FAMILY_SHAPE.items():
        columns = {f"{name}__isnull": False for name in required}
        columns.update({f"{name}__isnull": True for name in forbidden})
        branches.append(models.Q(kind=kind, **columns))
    return models.Q(*branches, _connector=models.Q.OR)


class ThreadStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    RESOLVED = "RESOLVED", "Resolved"


class GuidanceThread(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=32, choices=ThreadKind.choices)
    status = models.CharField(
        max_length=16, choices=ThreadStatus.choices, default=ThreadStatus.OPEN
    )
    # Nullable from 0003: a Faculty inquiry is about a Student without making the Student a
    # participant. The OFFICE and COUNSELING branches of `gm_thread_family_shape` still require it.
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="guidance_threads",
    )
    routing_college = models.ForeignKey(
        "organization.College", on_delete=models.PROTECT, null=True, blank=True
    )
    counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="counselor_guidance_threads",
    )
    relationship_appointment = models.OneToOneField(
        "appointments.Appointment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="guidance_thread",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assigned_guidance_threads",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_guidance_threads"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_sequence = models.PositiveBigIntegerField(default=0)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="resolved_guidance_threads",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    # Reserved-family participants and sources. Legacy kinds must leave all six null, enforced by
    # `_FAMILY_SHAPE`; no service path sets them yet, and no existing field or constraint moved.
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="requested_guidance_threads",
    )
    direct_first_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="direct_first_guidance_threads",
    )
    direct_second_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="direct_second_guidance_threads",
    )
    student_subject = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subject_guidance_threads",
    )
    relationship_referral = models.ForeignKey(
        "referrals.Referral",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="referral_guidance_threads",
    )
    relationship_case_grant = models.ForeignKey(
        "counseling.CounselorCaseContinuityGrant",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="case_grant_guidance_threads",
    )

    class Meta:
        default_permissions = ()
        ordering = ("-last_message_at", "-id")
        indexes = [
            models.Index(
                fields=("routing_college", "-last_message_at", "-id"),
                name="gm_office_directory_idx",
            ),
            models.Index(
                fields=("requester", "-last_message_at", "-id"),
                name="gm_inquiry_requester_idx",
                condition=models.Q(kind="FACULTY_INQUIRY"),
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=_family_shape_condition(), name="gm_thread_family_shape"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="OPEN", resolved_at__isnull=True, resolved_by__isnull=True)
                    | models.Q(
                        status="RESOLVED", resolved_at__isnull=False, resolved_by__isnull=False
                    )
                ),
                name="gm_thread_resolution_shape",
            ),
            models.CheckConstraint(
                condition=models.Q(last_sequence__gte=0), name="gm_thread_sequence_nonnegative"
            ),
            models.UniqueConstraint(
                fields=("student",),
                condition=models.Q(kind="OFFICE", status="OPEN"),
                name="gm_one_open_office_per_student",
            ),
            # A Counselor pair is stored once in canonical order, so the pair uniqueness below has
            # one row shape to match. Both columns are always null for every creatable kind today.
            models.CheckConstraint(
                condition=(
                    models.Q(direct_first_user__isnull=True, direct_second_user__isnull=True)
                    | models.Q(
                        direct_first_user__isnull=False,
                        direct_second_user__isnull=False,
                        direct_first_user__lt=models.F("direct_second_user"),
                    )
                ),
                name="gm_direct_pair_ordered",
            ),
            models.UniqueConstraint(
                fields=("relationship_referral",),
                condition=models.Q(kind="REFERRAL_COORDINATION"),
                name="gm_one_thread_per_referral",
            ),
            models.UniqueConstraint(
                fields=("direct_first_user", "direct_second_user"),
                condition=models.Q(kind="COUNSELOR_DIRECT"),
                name="gm_direct_pair_unique",
            ),
            models.UniqueConstraint(
                fields=("relationship_case_grant", "student_subject"),
                condition=models.Q(kind="COUNSELOR_CASE_COORDINATION"),
                name="gm_case_grant_subject_unique",
            ),
        ]


class GuidanceMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(GuidanceThread, on_delete=models.PROTECT, related_name="messages")
    sequence = models.PositiveBigIntegerField()
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sent_guidance_messages"
    )
    client_message_id = models.UUIDField()
    body_ciphertext = models.TextField()
    body_schema_version = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ("sequence",)
        constraints = [
            models.UniqueConstraint(
                fields=("thread", "sequence"), name="gm_message_thread_sequence_unique"
            ),
            models.UniqueConstraint(
                fields=("sender", "client_message_id"), name="gm_message_sender_client_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(sequence__gte=1), name="gm_message_sequence_positive"
            ),
        ]


class GuidanceThreadReadState(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(GuidanceThread, on_delete=models.PROTECT, related_name="read_states")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="guidance_read_states"
    )
    last_read_sequence = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=("thread", "user"), name="gm_read_thread_user_unique"),
            models.CheckConstraint(
                condition=models.Q(last_read_sequence__gte=0), name="gm_read_sequence_nonnegative"
            ),
        ]


class TemplateStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    ARCHIVED = "ARCHIVED", "Archived"


class GuidanceMessageTemplate(models.Model):
    """Reusable generic staff wording (ADR-104). It only prepares editable composer text.

    Not a Message and not a Student record: it is never encrypted with the Message keyring, never
    linked from a GuidanceMessage and never sent by itself. Wording must stay generic.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    body = models.TextField()
    status = models.CharField(
        max_length=16, choices=TemplateStatus.choices, default=TemplateStatus.ACTIVE
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_guidance_message_templates",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_guidance_message_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="archived_guidance_message_templates",
    )
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        default_permissions = ()
        ordering = (Lower("name"), "id")
        constraints = [
            models.UniqueConstraint(Lower("name"), name="gm_template_name_unique_ci"),
            models.CheckConstraint(
                condition=(
                    models.Q(status="ACTIVE", archived_by__isnull=True, archived_at__isnull=True)
                    | models.Q(
                        status="ARCHIVED", archived_by__isnull=False, archived_at__isnull=False
                    )
                ),
                name="gm_template_archive_shape",
            ),
            models.CheckConstraint(
                condition=~models.Q(name__regex=r"^\s*$"), name="gm_template_name_nonblank"
            ),
            models.CheckConstraint(
                condition=~models.Q(body__regex=r"^\s*$"), name="gm_template_body_nonblank"
            ),
            models.CheckConstraint(
                condition=LessThanOrEqual(Length("body"), 4000), name="gm_template_body_length"
            ),
        ]
