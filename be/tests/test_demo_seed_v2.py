"""Dataset v2 composition, encrypted boundaries, upgrades, and institutional schedule reuse."""

from collections import Counter
from contextlib import ExitStack
from datetime import date, datetime, time
from unittest.mock import patch

import pytest
from django.db import connection, transaction
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from compass.accounts.confidential_profile import read_account_profile_confidential_content
from compass.accounts.models import User
from compass.appointments.models import Appointment
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.availability.models import OfficeAvailabilityWindow, ProviderAvailabilityWindow
from compass.availability.services import (
    compute_base_availability,
    replace_office_weekly,
    replace_provider_weekly,
)
from compass.counseling.models import CounselingSharedSummary
from compass.counseling.shared_summary_content import read_shared_summary_content
from compass.demo_seed.accounts import plan_accounts, provision_accounts
from compass.demo_seed.cast import CAST, PERSONAS_BY_KEY, RICH_STUDENTS, STAFF, STUDENTS
from compass.demo_seed.config import load_demo_config
from compass.demo_seed.encryption import REQUIRED_KEYRINGS
from compass.demo_seed.history import seed_profiles
from compass.demo_seed.population import POPULATION
from compass.demo_seed.seed import seed_demo_staging, sync_prerequisites
from compass.demo_seed.support import DemoSeedConflict, DemoSeedError, SeedSession
from compass.demo_seed.timeline import EARLIEST_ANCHOR, LATEST_ANCHOR, resolve_timeline
from compass.exit_interviews.confidential_content import read_exit_interview_confidential_content
from compass.exit_interviews.models import ExitInterview
from compass.feedback.confidential_content import read_feedback_confidential_content
from compass.feedback.models import ClientSatisfactionResponse, CustomerFeedbackResponse
from compass.graduate_tracer.confidential_content import read_confidential_content as read_tracer
from compass.graduate_tracer.models import GraduateTracerResponse
from compass.inventory.confidential_content import read_confidential_content as read_inventory
from compass.inventory.models import StudentInventory
from compass.notifications.models import Notification
from compass.organization.academic_years import get_current_academic_year
from compass.organization.models import StudentAffiliation
from compass.referrals.confidential_content import (
    read_referral_action_remarks,
    read_referral_confidential_content,
)
from compass.referrals.models import Referral, ReferralAction
from compass.routine_interviews.models import RoutineInterview
from compass.student_support.services import get_student_support_context
from tests import test_demo_seed as demo

# Reuse the existing command environment fixture without collecting its TestCase again.
demo_env = demo.demo_env


def client_for(key):
    user = demo.demo_user(PERSONAS_BY_KEY[key])
    client = Client()
    client.cookies["compass_session"] = create_auth_session(user).token
    return client


def assert_encrypted(item, column, sentence):
    # Read the persisted SQL row, independently of the logical projection. Avoid emitting the
    # whole decrypted fixture on a failure; only ciphertext is read from the database.
    table = connection.ops.quote_name(item._meta.db_table)
    pk = connection.ops.quote_name(item._meta.pk.column)
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT row_to_json(t)::text FROM {table} t WHERE {pk} = %s", [item.pk])
        (stored,) = cursor.fetchone()
    assert bool(sentence)
    assert sentence not in stored
    assert getattr(item, column).startswith("gAAAAA")


class DemoV2CompositionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with patch.dict("os.environ", {"DEMO_ACCOUNT_PASSWORD": demo.DEMO_PASSWORD}):
            cls.report = seed_demo_staging(anchor=demo.ANCHOR)

    def test_population_and_ordinary_pagination_scope_search_filters(self):
        assert len(STUDENTS) == 57
        assert len(POPULATION) == 46
        assert Counter(p.lifecycle for p in STUDENTS) == {
            "CURRENT": 46,
            "GRADUATED": 8,
            "FORMER": 3,
        }
        assert Counter(p.college_code for p in STUDENTS) == {
            "CCMS": 15,
            "CAS": 16,
            "CBPA": 14,
            "COED": 12,
        }
        assert {
            year for p in STUDENTS for label, year in p.year_levels if label == "2026-2027"
        } == {1, 2, 3, 4, 5}
        assert StudentAffiliation.objects.count() == 46
        client = client_for("head_guidance")
        first = client.get("/api/v1/inventory/students")
        assert first.status_code == 200
        first = first.json()
        assert first["page_size"] == 20 and first["has_next"]
        second = client.get("/api/v1/inventory/students?page=2").json()
        assert len(first["items"]) == len(second["items"]) == 20
        assert {r["student"]["id"] for r in first["items"]}.isdisjoint(
            {r["student"]["id"] for r in second["items"]}
        )
        for key, count in (("counselor_a", 25), ("counselor_b", 21)):
            page = client_for(key).get("/api/v1/inventory/students?page_size=50").json()
            assert len(page["items"]) == count
        search = client.get("/api/v1/inventory/students?search=Reyes").json()
        assert len(search["items"]) == 1
        for status, count in (("SUBMITTED", 34), ("DRAFT", 8), ("MISSING", 4)):
            response = client.get(f"/api/v1/inventory/students?status={status}&page_size=50")
            assert response.status_code == 200
            assert len(response.json()["items"]) == count
        inventory = StudentInventory.objects.select_related("program").get(
            student=demo.demo_user(PERSONAS_BY_KEY["population_01"]),
            academic_year__is_current=True,
        )
        for query, field, value in (
            ("program_id", "program_id", inventory.program_id),
            ("college_id", "program__college_id", inventory.program.college_id),
            ("year_level", "year_level", inventory.year_level),
        ):
            response = client.get(f"/api/v1/inventory/students?{query}={value}&page_size=50")
            assert response.status_code == 200
            expected = (
                StudentAffiliation.objects.filter(college_id=value).count()
                if query == "college_id"
                else StudentInventory.objects.filter(
                    academic_year__is_current=True, **{field: value}
                ).count()
            )
            assert len(response.json()["items"]) == expected
        ascending = client.get("/api/v1/inventory/students?page_size=50&ordering=STUDENT_ASC")
        descending = client.get("/api/v1/inventory/students?page_size=50&ordering=STUDENT_DESC")
        assert ascending.status_code == descending.status_code == 200
        assert [r["student"]["id"] for r in ascending.json()["items"]] == list(
            reversed([r["student"]["id"] for r in descending.json()["items"]])
        )
        assert client_for("population_01").get("/api/v1/auth/session").status_code == 200

    def test_inventory_depth_children_drafts_and_support_mix(self):
        current = StudentInventory.objects.filter(academic_year__is_current=True)
        assert current.filter(submitted_at__isnull=False).count() == 34
        assert current.filter(submitted_at__isnull=True).count() == 8
        ordinary = concerned = 0
        indicators = set()
        for row in current.filter(submitted_at__isnull=False):
            support = get_student_support_context(
                actor=demo.demo_user(PERSONAS_BY_KEY["head_guidance"]), student_id=row.student_id
            )
            if support.indicators:
                concerned += 1
                indicators.update(i.code for i in support.indicators)
            else:
                ordinary += 1
        assert ordinary > concerned
        assert indicators == {
            "PWD",
            "FOUR_PS_BENEFICIARY",
            "INDIGENOUS_PEOPLES_MEMBER",
            "FATHER_DECEASED",
        }
        rows = {}
        for key in ("population_01", "population_29", "population_30", "population_31"):
            rows[key] = current.get(student=demo.demo_user(PERSONAS_BY_KEY[key]))
        detailed = rows["population_01"]
        assert detailed.family_members.count() == 2
        assert detailed.siblings.count() == 3
        assert detailed.education_entries.count() == 3
        assert (
            detailed.organization_memberships.exists() and detailed.transportation_entries.exists()
        )
        assert rows["population_29"].family_members.count() == 0
        assert rows["population_30"].family_members.count() == 0
        assert rows["population_31"].family_members.count() == 2
        assert read_inventory(rows["population_29"]).ambition_goal == ""
        assert read_inventory(rows["population_30"]).ambition_goal
        assert read_inventory(rows["population_31"]).current_concerns
        no_inventory = RoutineInterview.objects.get(
            student=demo.demo_user(PERSONAS_BY_KEY["population_38"])
        )
        assert no_inventory.inventory_id is None and no_inventory.intake_submitted_at is not None
        assert no_inventory.counseling_encounter_id is not None
        assert no_inventory.evaluation_finalized_at is None
        for key in ("population_20", "population_36", "population_44"):
            assert not Notification.objects.filter(
                recipient=demo.demo_user(PERSONAS_BY_KEY[key])
            ).exists()

    def test_v2_feedback_has_optional_text_and_report_counts(self):
        customers = list(CustomerFeedbackResponse.objects.all())
        assert len(customers) == 6
        assert (
            sum(
                bool(read_feedback_confidential_content(row).additional_feedback)
                for row in customers
            )
            == 5
        )
        csm = list(ClientSatisfactionResponse.objects.all())
        assert len(csm) == 6
        assert sum(bool(read_feedback_confidential_content(row).suggestions) for row in csm) == 5
        assert dict(self.report.records)["Customer Feedback"] == "6"
        assert dict(self.report.records)["CSM responses"] == "6"
        assert all(demo.demo_user(p).get_full_name() == p.full_name for p in STUDENTS)

    def test_exit_and_tracer_variety(self):
        exits = ExitInterview.objects.all()
        assert exits.filter(status="DRAFT").count() == 3
        assert exits.filter(status="SUBMITTED").count() == 10
        early = exits.get(student=demo.demo_user(PERSONAS_BY_KEY["population_04"]))
        nearly = exits.get(student=demo.demo_user(PERSONAS_BY_KEY["population_07"]))
        assert early.self_assessment_ratings.count() == 0
        assert nearly.self_assessment_ratings.count() == 15
        assert len(set(nearly.self_assessment_ratings.values_list("rating", flat=True))) == 3
        tracers = GraduateTracerResponse.objects.all()
        assert tracers.filter(status="SUBMITTED").count() == 6
        assert tracers.filter(status="DRAFT").count() == 1
        assert set(
            tracers.filter(status="SUBMITTED").values_list("current_employment_state", flat=True)
        ) == {"EMPLOYED", "NOT_EMPLOYED", "NEVER_EMPLOYED"}
        assert tracers.filter(present_employment_status="SELF_EMPLOYED").exists()
        assert tracers.filter(first_job_related_to_course=False).exists()
        assert not tracers.filter(student=demo.demo_user(PERSONAS_BY_KEY["population_44"])).exists()

    def test_all_confidential_domains_round_trip_and_sql_ciphertext(self):
        user = demo.demo_user(PERSONAS_BY_KEY["population_03"])
        profile = read_account_profile_confidential_content(user)
        assert profile.contact_number == "DEMO-CONTACT-03"
        assert_encrypted(user, "profile_confidential_content_ciphertext", profile.current_address)
        item = StudentInventory.objects.get(student=user, academic_year__is_current=True)
        assert_encrypted(
            item, "confidential_content_ciphertext", read_inventory(item).current_concerns
        )
        parent = item.family_members.first()
        assert_encrypted(parent, "confidential_content_ciphertext", read_inventory(parent).name)
        school = item.education_entries.first()
        assert_encrypted(
            school,
            "confidential_content_ciphertext",
            read_inventory(school).school_attended_address,
        )
        summary = CounselingSharedSummary.objects.filter(published_at__isnull=False).first()
        assert_encrypted(summary, "content_ciphertext", read_shared_summary_content(summary))
        referral = Referral.objects.filter(voided_at__isnull=True).first()
        content = read_referral_confidential_content(referral)
        assert_encrypted(referral, "confidential_content_ciphertext", content.reason)
        action = ReferralAction.objects.first()
        assert_encrypted(action, "remarks_ciphertext", read_referral_action_remarks(action))
        exit_item = ExitInterview.objects.filter(status="SUBMITTED").first()
        assert_encrypted(
            exit_item,
            "confidential_content_ciphertext",
            read_exit_interview_confidential_content(exit_item).faculty_comments,
        )
        tracer = GraduateTracerResponse.objects.filter(status="SUBMITTED").first()
        assert_encrypted(
            tracer,
            "confidential_content_ciphertext",
            read_tracer(tracer).curriculum_improvement_suggestions,
        )
        customer = CustomerFeedbackResponse.objects.first()
        assert_encrypted(
            customer,
            "confidential_content_ciphertext",
            read_feedback_confidential_content(customer).additional_feedback,
        )
        csm = ClientSatisfactionResponse.objects.first()
        assert_encrypted(
            csm,
            "confidential_content_ciphertext",
            read_feedback_confidential_content(csm).suggestions,
        )
        profile_api = client_for("population_03").get("/api/v1/me/profile")
        assert profile_api.status_code == 200
        assert profile_api.json()["contact_number"] == "DEMO-CONTACT-03"
        inventory_api = client_for("population_03").get("/api/v1/inventory/me/current")
        assert inventory_api.status_code == 200
        assert (
            client_for("head_guidance")
            .get(f"/api/v1/feedback/customer-feedback/responses/{customer.pk}")
            .status_code
            == 200
        )


@pytest.mark.django_db
@pytest.mark.parametrize("name", REQUIRED_KEYRINGS)
@pytest.mark.parametrize("value", ([], ["invalid-key"]))
def test_keyring_preflight_fails_before_any_write(demo_env, name, value):
    with override_settings(**{name: value}), pytest.raises(DemoSeedError, match=name):
        seed_demo_staging()
    assert User.objects.count() == AuditEvent.objects.count() == 0


@pytest.mark.django_db
def test_same_role_name_collision_preserves_the_existing_identity(demo_env):
    session = provision_for_schedule()
    user = session.user("population_01")
    user.first_name = "Existing identity"
    user.save(update_fields=["first_name"])
    before = demo._snapshot()
    with pytest.raises(DemoSeedConflict, match="population_01.*different canonical name"):
        seed_demo_staging()
    user.refresh_from_db()
    assert user.first_name == "Existing identity"
    assert demo._snapshot() == before


@pytest.mark.django_db
def test_population_unit_failure_rolls_back_and_rerun_resumes(demo_env):
    from compass.demo_seed import population_workflows

    original = population_workflows.seed_annual_inventory

    def fail_after_write(session, persona, label):
        original(session, persona, label)
        if persona.key == "population_06":
            raise DemoSeedError("controlled population-unit interruption")

    with patch.object(population_workflows, "seed_annual_inventory", side_effect=fail_after_write):
        with pytest.raises(DemoSeedError, match="controlled population-unit interruption"):
            seed_demo_staging()
    assert not StudentInventory.objects.filter(
        student=demo.demo_user(PERSONAS_BY_KEY["population_06"])
    ).exists()
    assert get_current_academic_year().label == "2026-2027"
    preserved = list(StudentInventory.objects.order_by("pk").values())
    report = seed_demo_staging()
    assert report.dataset_version == 2
    ids = [row["id"] for row in preserved]
    assert list(StudentInventory.objects.filter(pk__in=ids).order_by("pk").values()) == preserved
    snapshot = demo._snapshot()
    seed_demo_staging()
    assert demo._snapshot() == snapshot


@pytest.mark.django_db
def test_v1_to_v2_is_additive_preserves_history_and_changed_password(demo_env):
    # Reconstruct the v1 cohort with today's owning services. Availability correction lets that
    # original world complete; all v1 identities, narratives, natural keys and markers are kept.
    with ExitStack() as stack:
        for target, value in (
            ("accounts.CAST", (*STAFF, *RICH_STUDENTS)),
            ("seed.CAST", (*STAFF, *RICH_STUDENTS)),
            ("seed.STUDENTS", RICH_STUDENTS),
            ("configuration.STUDENTS", RICH_STUDENTS),
            ("history.STUDENTS", RICH_STUDENTS),
            ("seed.DEMO_DATASET_VERSION", 1),
        ):
            stack.enter_context(patch(f"compass.demo_seed.{target}", value))
        stack.enter_context(patch("compass.demo_seed.seed.seed_population_forms"))
        stack.enter_context(patch("compass.demo_seed.seed.seed_secondary_stories"))
        stack.enter_context(
            patch("compass.demo_seed.seed.population_feedback.seed_population_feedback")
        )
        seed_demo_staging()
    old_user = demo.demo_user(PERSONAS_BY_KEY["second_year"])
    old_user.set_password("a different established demo password")
    old_user.save(update_fields=["password"])
    models = (
        StudentInventory,
        Appointment,
        RoutineInterview,
        ExitInterview,
        GraduateTracerResponse,
        CounselingSharedSummary,
        Referral,
        CustomerFeedbackResponse,
    )
    originals = {model: list(model.objects.order_by("pk").values()) for model in models}
    upgraded = seed_demo_staging()
    assert upgraded.dataset_version == 2
    assert User.objects.filter(role__code="STUDENT").count() == 57
    for model, rows in originals.items():
        ids = [row["id"] for row in rows]
        assert list(model.objects.filter(pk__in=ids).order_by("pk").values()) == rows
    assert old_user.__class__.objects.get(pk=old_user.pk).check_password(
        "a different established demo password"
    )
    snapshot = demo._snapshot()
    repeat = seed_demo_staging()
    assert demo._snapshot() == snapshot and sum(repeat.created.values()) == 0


def provision_for_schedule():
    sync_prerequisites()
    config = load_demo_config(app_env="local-staging")
    session = SeedSession(timeline=resolve_timeline(), app_env="local-staging")
    with transaction.atomic():
        plans = plan_accounts(config)
        provision_accounts(session, plans, config)
        seed_profiles(session, created_keys={plan.persona.key for plan in plans})
    return session


@pytest.mark.django_db
def test_compatible_institutional_availability_is_preserved(demo_env):
    session = provision_for_schedule()
    windows = [
        {"weekday": day, "start_time": time(11), "end_time": time(16), "mode_scope": "ALL"}
        for day in ("MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY")
    ]
    replace_office_weekly(windows=windows, context=session.system())
    replace_provider_weekly(
        provider_id=session.users["counselor_a"].pk, windows=windows, context=session.system()
    )
    office = list(OfficeAvailabilityWindow.objects.order_by("pk").values())
    provider = list(
        ProviderAvailabilityWindow.objects.filter(provider=session.users["counselor_a"])
        .order_by("pk")
        .values()
    )
    seed_demo_staging()
    assert list(OfficeAvailabilityWindow.objects.order_by("pk").values()) == office
    assert (
        list(
            ProviderAvailabilityWindow.objects.filter(provider=session.users["counselor_a"])
            .order_by("pk")
            .values()
        )
        == provider
    )
    for item in Appointment.objects.select_related("service"):
        day = timezone.localtime(item.starts_at).date()
        base = compute_base_availability(
            provider_id=item.provider_id,
            service_id=item.service_id,
            delivery_mode=item.delivery_mode,
            start_date=day,
            end_date=day + demo.timedelta(days=1),
        )
        assert any(w.starts_at <= item.starts_at < item.ends_at <= w.ends_at for w in base.windows)


@pytest.mark.django_db
def test_incompatible_availability_fails_closed_and_does_not_overwrite(demo_env):
    windows = [
        {"weekday": day, "start_time": time(8), "end_time": time(8, 30), "mode_scope": "ALL"}
        for day in ("MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY")
    ]
    replace_office_weekly(windows=windows, context=AuditContext.system())
    before = list(OfficeAvailabilityWindow.objects.order_by("pk").values())
    with pytest.raises(
        DemoSeedConflict, match="SCENARIO_COMPLETED_COUNSELING.*no compatible Appointment slot"
    ):
        seed_demo_staging()
    assert list(OfficeAvailabilityWindow.objects.order_by("pk").values()) == before
    assert not Appointment.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("anchor", (EARLIEST_ANCHOR, date(2026, 10, 8), LATEST_ANCHOR))
def test_anchor_matrix_seeds_valid_intervals(demo_env, anchor):
    timeline = resolve_timeline(anchor=anchor)
    simulated_now = datetime.combine(anchor, time(23), tzinfo=timeline.zone)
    with patch("django.utils.timezone.now", return_value=simulated_now):
        report = seed_demo_staging(anchor=anchor)
    assert report.anchor == anchor
    assert len(report.accounts) == len(CAST)
    assert not Appointment.objects.filter(
        starts_at__gte=timezone.make_aware(datetime.combine(anchor, time())),
        status__in=["COMPLETED", "NO_SHOW", "CANCELLED"],
    ).exists()
