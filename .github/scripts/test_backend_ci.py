"""Self-tests for backend CI selection and sharding. Run: python3 -m unittest discover .github/scripts"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import backend_ci  # noqa: E402


def selected(*paths: str) -> backend_ci.Selection:
    return backend_ci.select(list(paths))


class SelectionTests(unittest.TestCase):
    def test_guidance_operations_and_sources_select_aggregate_regressions(self):
        for source in ("guidance_operations", "guidance_messages", "routine_interviews",
                       "good_moral", "call_slips", "appointments",
                       "overview", "work_queue", "service_catalog"):
            result = selected(f"be/compass/{source}/services.py")
            self.assertFalse(result.full)
            self.assertIn("test_guidance_operations.py", result.files)
        # Organization and identity policy are shared scope infrastructure and keep the full gate.
        self.assertTrue(selected("be/compass/organization/access_scope.py").full)
        result = selected("be/compass/guidance_operations/api.py")
        for name in ("test_work_queue.py", "test_overview.py", "test_guidance_messages.py",
                     "test_routine_interviews.py", "test_good_moral.py", "test_call_slips.py",
                     "test_appointment_management_scope.py", "test_accounts.py",
                     "test_openapi_contract.py"):
            self.assertIn(name, result.files)
        self.assertNotIn("test_demo_seed.py", result.files)

    def test_operations_frontend_presentation_does_not_select_backend_domains(self):
        result = selected("fe/src/features/guidance-operations/guidance-operations-page.tsx")
        self.assertFalse(result.full)
        self.assertNotIn("test_guidance_operations.py", result.files)

    def test_assessment_records_selects_its_actual_boundaries(self):
        for path in ("services.py", "api.py", "confidential_content.py", "models.py",
                     "management/commands/rotate_assessment_record_confidential_content.py"):
            result = selected("be/compass/assessment_records/" + path)
            self.assertFalse(result.full)
            for name in ("test_assessment_records.py", "test_assessment_records_configuration.py",
                         "test_capability_dependencies.py", "test_operational_students.py",
                         "test_confidential_data_crypto.py", "test_audit.py",
                         "test_runtime_secrets.py", "test_runtime_secrets_compose.py",
                         "test_openapi_contract.py"):
                self.assertIn(name, result.files)
            self.assertNotIn("test_student_support.py", result.files)
        self.assertTrue(selected("be/compass/assessment_records/migrations/0001_initial.py").full)

    def test_assessment_shared_changes_remain_conservative(self):
        for path in ("be/compass/accounts/policy.py", "be/compass/audit/actions.py"):
            self.assertTrue(selected(path).full)
        self.assertIn("test_runtime_secrets.py", selected("be/compose.staging.yaml").files)
        self.assertIn("test_openapi_contract.py", selected("contracts/openapi.json").files)
        for path in ("fe/src/features/assessment-records/assessment-records-list.tsx",
                     "fe/src/features/portal/components/portal-workspaces.ts"):
            self.assertFalse(selected(path).full)
            self.assertNotIn("test_assessment_records.py", selected(path).files)

    def test_guidance_messages_reaches_all_boundaries(self):
        for path in ("services.py", "policy.py", "content.py", "api.py", "models.py", "templates.py"):
            result = selected("be/compass/guidance_messages/" + path)
            self.assertFalse(result.full)
            for name in (
                "test_guidance_messages.py",
                "test_guidance_messages_concurrency.py",
                "test_guidance_messages_handlers.py",
                "test_guidance_messages_realtime.py",
                "test_guidance_messages_templates.py",
                "test_capability_dependencies.py",
                "test_openapi_contract.py",
                "test_operational_students.py",
                "test_appointments.py",
                "test_counseling_context.py",
                "test_realtime_service.py",
                "test_runtime_secrets.py",
            ):
                self.assertIn(name, result.files)
        self.assertTrue(selected("be/compass/guidance_messages/migrations/0001_initial.py").full)
        self.assertTrue(
            selected("be/compass/guidance_messages/migrations/0002_guidance_message_template.py").full
        )

    def test_student_actions_and_domain_sources_select_projection_regressions(self):
        for source in (
            "student_actions", "inventory", "routine_interviews", "exit_interviews",
            "graduate_tracer", "call_slips", "ecounseling", "guidance_messages", "overview",
            "appointments", "service_catalog", "counseling",
        ):
            result = selected(f"be/compass/{source}/student_actions.py")
            self.assertFalse(result.full)
            self.assertIn("test_student_actions.py", result.files)
            self.assertNotIn("test_demo_seed.py", result.files)
        composition = selected("be/compass/student_actions/services.py")
        for name in ("test_inventory.py", "test_routine_interviews.py", "test_exit_interviews.py",
                     "test_graduate_tracer.py", "test_call_slips.py", "test_ecounseling.py",
                     "test_guidance_messages.py", "test_notifications.py", "test_accounts.py",
                     "test_capability_dependencies.py"):
            self.assertIn(name, composition.files)

    def test_work_queue_and_source_changes_select_projection_regressions(self):
        for path in (
            "be/compass/work_queue/services.py",
            "be/compass/guidance_messages/work.py",
            "be/compass/guidance_messages/management/commands/rotate_guidance_message_encryption.py",
            "be/compass/routine_interviews/work.py",
            "be/compass/good_moral/work.py",
            "be/compass/call_slips/work.py",
            "be/compass/overview/services.py",
        ):
            result = selected(path)
            self.assertFalse(result.full)
            self.assertIn("test_work_queue.py", result.files)
        self.assertIn(
            "test_guidance_messages_rotation.py", selected("be/compass/work_queue/api.py").files
        )
        self.assertNotIn("test_demo_seed.py", selected("be/compass/work_queue/services.py").files)
        self.assertIn(
            "test_runtime_secrets.py",
            selected("be/deploy/runtime-secrets/runtime_secrets.py").files,
        )

    def test_staff_operations_policy_and_audit_changes_select_the_full_suite(self):
        # The template capability lives in identity policy; template audit actions in audit.
        self.assertTrue(selected("be/compass/accounts/policy.py").full)
        self.assertTrue(selected("be/compass/audit/actions.py").full)

    def test_new_messages_test_files_run_when_changed(self):
        for name in ("test_guidance_messages_handlers.py", "test_guidance_messages_templates.py"):
            result = selected("be/tests/" + name)
            self.assertFalse(result.full)
            self.assertIn(name, result.files)

    def test_safety_bundle_always_runs(self):
        result = selected("be/docs/decisions/ADR-001-example.md")
        self.assertFalse(result.full)
        self.assertEqual(result.bundles, ["safety"])
        self.assertIn("test_openapi_contract.py", result.files)
        self.assertIn("test_institutional_time.py", result.files)

    def test_inventory_change_reaches_its_consumers(self):
        result = selected("be/compass/inventory/services.py")
        self.assertFalse(result.full)
        for name in (
            "test_inventory.py",
            "test_inventory_confidential_content_encryption.py",
            "test_inventory_counselor_review.py",
            "test_program_inventory_academic_context.py",
            "test_routine_inventory_decoupling.py",
            "test_inventory_counseling_regression.py",
            "test_counseling_context.py",
            "test_good_moral.py",
            "test_exit_interviews.py",
            "test_student_support.py",
            "test_student_profiling_reports.py",
            "test_appointments.py",
        ):
            self.assertIn(name, result.files)
        self.assertNotIn("test_demo_seed.py", result.files)

    def test_counseling_change_reaches_routine_feedback_and_appointments(self):
        result = selected("be/compass/counseling/services.py")
        for name in (
            "test_counseling.py",
            "test_counseling_context.py",
            "test_counseling_downstream_lifecycle.py",
            "test_routine_encounter_linking.py",
            "test_feedback.py",
            "test_appointments.py",
            "test_call_slips.py",
        ):
            self.assertIn(name, result.files)

    def test_good_moral_change_reaches_exit_interviews_feedback_and_documents(self):
        result = selected("be/compass/good_moral/services.py")
        for name in (
            "test_good_moral.py",
            "test_good_moral_preparation.py",
            "test_exit_interview_opportunities.py",
            "test_feedback.py",
            "test_documents.py",
            "test_privacy_release_audit.py",
        ):
            self.assertIn(name, result.files)

    def test_referral_change_reaches_call_slips(self):
        result = selected("be/compass/referrals/services.py")
        for name in ("test_referrals.py", "test_call_slips.py", "test_referral_call_slip_lifecycle.py"):
            self.assertIn(name, result.files)

    def test_availability_change_reaches_reservations_and_slots(self):
        result = selected("be/compass/availability/services.py")
        for name in (
            "test_availability.py",
            "test_availability_reservation_neutrality.py",
            "test_appointment_slot_reservations.py",
            "test_appointments.py",
            "test_service_provider_qualification.py",
        ):
            self.assertIn(name, result.files)

    def test_ecounseling_change_reaches_media_and_retention(self):
        result = selected("be/compass/ecounseling/media.py")
        for name in ("test_ecounseling.py", "test_ecounseling_media_v2.py", "test_operational_retention.py"):
            self.assertIn(name, result.files)

    def test_privacy_governance_change_reaches_retention_and_media(self):
        result = selected("be/compass/privacy_governance/retention.py")
        for name in (
            "test_operational_retention.py",
            "test_ecounseling_media_v2.py",
            "test_graduate_tracer_confidential_content_encryption.py",
        ):
            self.assertIn(name, result.files)

    def test_shared_infrastructure_selects_the_complete_suite(self):
        for path in (
            "be/compass/common/institutional_time.py",
            "be/compass/accounts/models.py",
            "be/compass/authentication/sessions.py",
            "be/compass/audit/services.py",
            "be/compass/confidential_data/crypto.py",
            "be/compass/notifications/services.py",
            "be/compass/organization/models.py",
            "be/compass/api/v1/router.py",
            "be/config/settings.py",
            "be/pyproject.toml",
            "be/uv.lock",
            "be/tests/conftest.py",
            "be/tests/settings.py",
            "be/compass/inventory/migrations/0099_example.py",
            "be/compass/tasks.py",
        ):
            with self.subTest(path=path):
                result = selected(path)
                self.assertTrue(result.full)
                self.assertEqual(result.files, backend_ci.all_test_files())

    def test_unknown_backend_paths_expand_to_the_complete_suite(self):
        for path in (
            "be/compass/brand_new_domain/services.py",
            "be/compass/integrations/new_client.py",
            "be/tests/fixtures/data.json",
            "be/some_new_tool.py",
        ):
            with self.subTest(path=path):
                self.assertTrue(selected(path).full)

    def test_one_full_path_makes_the_whole_selection_full(self):
        result = selected("be/compass/announcements/services.py", "be/compass/common/errors.py")
        self.assertTrue(result.full)

    def test_test_helper_selects_its_transitive_importers(self):
        result = selected("be/tests/inventory_test_helpers.py")
        self.assertFalse(result.full)
        self.assertIn("test_inventory.py", result.files)
        # test_routine_encounter_linking imports the helper through test_routine_interviews.
        self.assertIn("test_routine_encounter_linking.py", result.files)

    def test_changed_test_module_selects_itself_and_its_importers(self):
        result = selected("be/tests/test_feedback.py")
        self.assertIn("test_feedback.py", result.files)
        self.assertIn("test_collection_ordering.py", result.files)

    def test_deleted_test_files_are_not_passed_to_pytest(self):
        result = selected("be/tests/test_removed_long_ago.py")
        self.assertNotIn("test_removed_long_ago.py", result.files)

    def test_frontend_only_paths_do_not_affect_backend_selection(self):
        result = selected("fe/src/app/page.tsx")
        self.assertEqual(result.bundles, ["safety"])
        self.assertEqual(result.areas, {})

    def test_deployment_files_select_runtime_tests(self):
        result = selected("be/compose.staging.yaml")
        self.assertIn("test_runtime_secrets_compose.py", result.files)

    def test_realtime_service_selects_realtime_tests_without_the_complete_suite(self):
        result = selected("be/realtime_service/app.py")
        self.assertFalse(result.full)
        self.assertIn("test_realtime_service.py", result.files)
        self.assertIn("test_realtime_isolation.py", result.files)
        protocol = selected("be/realtime_service/protocol.py")
        self.assertIn("test_notification_realtime.py", protocol.files)
        ticket_api = selected("be/compass/realtime/api.py")
        self.assertFalse(ticket_api.full)
        self.assertIn("test_realtime_tickets.py", ticket_api.files)
        self.assertIn("test_authentication.py", ticket_api.files)


class ShardingTests(unittest.TestCase):
    def test_full_regression_covers_every_test_file_exactly_once(self):
        self.assertEqual(backend_ci.verify(), [])

    def test_split_files_are_spread_over_parts(self):
        buckets = backend_ci.plan(backend_ci.all_test_files(), backend_ci.FULL_SHARDS, backend_ci.load_weights())
        parts = [
            item.part
            for bucket in buckets
            for item in bucket
            if item.file == "test_inventory_confidential_content_encryption.py"
        ]
        self.assertEqual(sorted(parts), [0, 1, 2, 3])

    def test_plan_is_deterministic_and_balanced(self):
        weights = backend_ci.load_weights()
        first = backend_ci.plan(backend_ci.all_test_files(), backend_ci.FULL_SHARDS, weights)
        second = backend_ci.plan(backend_ci.all_test_files(), backend_ci.FULL_SHARDS, weights)
        self.assertEqual(first, second)

        def load(bucket):
            return sum(max(weights.get(i.file, backend_ci.DEFAULT_TEST_SECONDS), 1.0) / i.parts for i in bucket)

        loads = [load(bucket) for bucket in first]
        self.assertLess(max(loads) - min(loads), 0.15 * max(loads))

    def test_new_untimed_file_still_lands_in_exactly_one_shard(self):
        files = [*backend_ci.all_test_files(), "test_brand_new_feature.py"]
        buckets = backend_ci.plan(files, backend_ci.FULL_SHARDS, backend_ci.load_weights())
        homes = [i for i, bucket in enumerate(buckets) for item in bucket if item.file == "test_brand_new_feature.py"]
        self.assertEqual(len(homes), 1)

    def test_targeted_shard_count_scales_with_selected_runtime(self):
        weights = backend_ci.load_weights()
        small = selected("be/compass/announcements/services.py").files
        large = selected("be/compass/inventory/services.py").files
        self.assertEqual(backend_ci.shard_count_for(small, weights), 1)
        self.assertEqual(backend_ci.shard_count_for(large, weights), backend_ci.TARGETED_MAX_SHARDS)


if __name__ == "__main__":
    unittest.main()
