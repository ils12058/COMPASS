# CANON-1 migration graph inventory

Verified against `d353108d1f757386b9020c4d1297e081258d2e4e` on 2026-10-16 (Asia/Manila). No migration files are changed by CANON-1A.

## Inventory

102 numbered migrations across 27 apps; 8 frozen helper modules. The static AST inventory contains 47 RunPython constructor sites in 36 files, no RunSQL constructors, and one empty Good Moral merge migration. Constructor counts are not executed operation counts: comprehensions create multiple field/constraint operations. See [complete inventory](evidence/migration-inventory.json) for every dependency expression and custom Python callable.

| App | Numbered files |
| --- | ---: |
| accounts | 8 |
| announcements | 2 |
| appointments | 3 |
| assessment_records | 1 |
| audit | 3 |
| authentication | 2 |
| availability | 1 |
| call_slips | 3 |
| counseling | 5 |
| documents | 2 |
| ecounseling | 6 |
| exit_interviews | 6 |
| feedback | 4 |
| good_moral | 7 |
| graduate_tracer | 5 |
| guidance_messages | 2 |
| institutional_forms | 7 |
| inventory | 8 |
| notifications | 2 |
| organization | 3 |
| platform_ops | 1 |
| privacy_governance | 6 |
| referrals | 4 |
| resources | 2 |
| routine_interviews | 4 |
| service_catalog | 4 |
| student_support | 1 |

## Every migration dependency

Dependencies below are the literal source expressions, including swappable user-model dependencies. Arrows in these expressions identify prerequisites, not runtime import direction.

| Migration | Dependencies |
| --- | --- |
| `be/compass/accounts/migrations/0001_initial.py` | `[]` |
| `be/compass/accounts/migrations/0002_user_reusable_profile_fields.py` | `[('accounts', '0001_initial')]` |
| `be/compass/accounts/migrations/0003_user_student_lifecycle_status.py` | `[('accounts', '0002_user_reusable_profile_fields')]` |
| `be/compass/accounts/migrations/0004_user_email_verified_at.py` | `[('accounts', '0003_user_student_lifecycle_status')]` |
| `be/compass/accounts/migrations/0005_user_institutional_id.py` | `[('accounts', '0004_user_email_verified_at')]` |
| `be/compass/accounts/migrations/0006_rename_reference_capabilities.py` | `[('accounts', '0005_user_institutional_id')]` |
| `be/compass/accounts/migrations/0007_encrypt_confidential_content.py` | `[('accounts', '0006_rename_reference_capabilities')]` |
| `be/compass/accounts/migrations/0008_remove_plaintext_confidential_content.py` | `[('accounts', '0007_encrypt_confidential_content')]` |
| `be/compass/announcements/migrations/0001_initial.py` | `[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/announcements/migrations/0002_alter_announcement_audience.py` | `[('announcements', '0001_initial')]` |
| `be/compass/appointments/migrations/0001_initial.py` | `[migrations.swappable_dependency(settings.AUTH_USER_MODEL), ('service_catalog', '0002_service_cancellation_cutoff')]` |
| `be/compass/appointments/migrations/0002_lifecycle_completion.py` | `[('appointments', '0001_initial'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/appointments/migrations/0003_service_name_snapshot.py` | `[('appointments', '0002_lifecycle_completion'), ('service_catalog', '0003_service_requires_current_inventory')]` |
| `be/compass/assessment_records/migrations/0001_initial.py` | `[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/audit/migrations/0001_initial.py` | `[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/audit/migrations/0002_alter_auditevent_metadata.py` | `[('audit', '0001_initial')]` |
| `be/compass/audit/migrations/0003_allow_underscores_in_action_codes.py` | `[('audit', '0002_alter_auditevent_metadata'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/authentication/migrations/0001_initial.py` | `[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/authentication/migrations/0002_email_change_request.py` | `[('authentication', '0001_initial')]` |
| `be/compass/availability/migrations/0001_initial.py` | `[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/call_slips/migrations/0001_initial.py` | `[migrations.swappable_dependency(settings.AUTH_USER_MODEL), ('institutional_forms', '0005_call_slip_family'), ('referrals', '0001_initial')]` |
| `be/compass/call_slips/migrations/0002_void_and_reissue.py` | `[('call_slips', '0001_initial'), ('referrals', '0002_void_provenance'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/call_slips/migrations/0003_callslip_issuance_mode.py` | `[('call_slips', '0002_void_and_reissue'), ('notifications', '0001_initial')]` |
| `be/compass/counseling/migrations/0001_initial.py` | `[migrations.swappable_dependency(settings.AUTH_USER_MODEL), ('appointments', '0001_initial'), ('service_catalog', '0002_service_cancellation_cutoff')]` |
| `be/compass/counseling/migrations/0002_counselingsharedsummary.py` | `[('counseling', '0001_initial')]` |
| `be/compass/counseling/migrations/0003_service_name_snapshot.py` | `[('counseling', '0002_counselingsharedsummary'), ('service_catalog', '0003_service_requires_current_inventory')]` |
| `be/compass/counseling/migrations/0004_encrypt_shared_summary_content.py` | `[('counseling', '0003_service_name_snapshot')]` |
| `be/compass/counseling/migrations/0005_remove_plaintext_shared_summary_content.py` | `[('counseling', '0004_encrypt_shared_summary_content')]` |
| `be/compass/documents/migrations/0001_initial.py` | `[]` |
| `be/compass/documents/migrations/0002_remove_documentbrandingprofile.py` | `[('documents', '0001_initial')]` |
| `be/compass/ecounseling/migrations/0001_initial.py` | `[('appointments', '0001_initial')]` |
| `be/compass/ecounseling/migrations/0002_consent_media_capture.py` | `[('accounts', '0001_initial'), ('ecounseling', '0001_initial')]` |
| `be/compass/ecounseling/migrations/0003_ecounselingmediacapture_artifact_disposed_at.py` | `[('ecounseling', '0002_consent_media_capture')]` |
| `be/compass/ecounseling/migrations/0004_ecounselingmediaartifact_and_more.py` | `[('appointments', '0003_service_name_snapshot'), ('ecounseling', '0003_ecounselingmediacapture_artifact_disposed_at')]` |
| `be/compass/ecounseling/migrations/0005_capture_reconciliation.py` | `[('ecounseling', '0004_ecounselingmediaartifact_and_more')]` |
| `be/compass/ecounseling/migrations/0006_webhook_provenance.py` | `[('ecounseling', '0005_capture_reconciliation')]` |
| `be/compass/exit_interviews/migrations/0001_initial.py` | `[('accounts', '0002_user_reusable_profile_fields'), ('inventory', '0001_initial'), ('organization', '0002_academic_year'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/exit_interviews/migrations/0002_exitinterviewopportunity_exitinterview_opportunity_and_more.py` | `[('exit_interviews', '0001_initial'), ('organization', '0003_program'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/exit_interviews/migrations/0003_encrypt_confidential_content.py` | `[('exit_interviews', '0002_exitinterviewopportunity_exitinterview_opportunity_and_more')]` |
| `be/compass/exit_interviews/migrations/0004_remove_plaintext_confidential_content.py` | `[('exit_interviews', '0003_encrypt_confidential_content')]` |
| `be/compass/exit_interviews/migrations/0005_saved_form_revision.py` | `[('exit_interviews', '0004_remove_plaintext_confidential_content'), ('institutional_forms', '0007_customer_feedback_family')]` |
| `be/compass/exit_interviews/migrations/0006_exitinterviewreopenevent_targets_ciphertext.py` | `[('exit_interviews', '0005_saved_form_revision')]` |
| `be/compass/feedback/migrations/0001_initial.py` | `[('institutional_forms', '0007_customer_feedback_family')]` |
| `be/compass/feedback/migrations/0002_feedback_opportunity.py` | `[('accounts', '0006_rename_reference_capabilities'), ('feedback', '0001_initial')]` |
| `be/compass/feedback/migrations/0003_encrypt_confidential_content.py` | `[('feedback', '0002_feedback_opportunity')]` |
| `be/compass/feedback/migrations/0004_remove_plaintext_confidential_content.py` | `[('feedback', '0003_encrypt_confidential_content')]` |
| `be/compass/good_moral/migrations/0001_initial.py` | `[('institutional_forms', '0006_good_moral_families'), ('inventory', '0001_initial'), ('organization', '0002_academic_year'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/good_moral/migrations/0002_request_cancellation.py` | `[('good_moral', '0001_initial'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/good_moral/migrations/0003_request_creation_identity.py` | `[('good_moral', '0002_request_cancellation')]` |
| `be/compass/good_moral/migrations/0004_goodmoralrequest_exit_interview_and_more.py` | `[('exit_interviews', '0002_exitinterviewopportunity_exitinterview_opportunity_and_more'), ('good_moral', '0003_request_creation_identity'), ('institutional_forms', '0007_customer_feedback_family'), ('inventory', '0005_submission_history_reopen'), ('organization', '0003_program'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/good_moral/migrations/0004_remove_goodmoralrequest_good_moral_issuance_shape_and_more.py` | `[('good_moral', '0003_request_creation_identity'), ('institutional_forms', '0007_customer_feedback_family'), ('inventory', '0005_submission_history_reopen'), ('organization', '0003_program'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/good_moral/migrations/0005_merge_20261005_0419.py` | `[('good_moral', '0004_goodmoralrequest_exit_interview_and_more'), ('good_moral', '0004_remove_goodmoralrequest_good_moral_issuance_shape_and_more')]` |
| `be/compass/good_moral/migrations/0006_initiation_provenance.py` | `[('good_moral', '0005_merge_20261005_0419'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/graduate_tracer/migrations/0001_initial.py` | `[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/graduate_tracer/migrations/0002_graduatetracerdisposedparticipation_and_more.py` | `[('graduate_tracer', '0001_initial'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/graduate_tracer/migrations/0003_encrypt_confidential_content.py` | `[('graduate_tracer', '0002_graduatetracerdisposedparticipation_and_more')]` |
| `be/compass/graduate_tracer/migrations/0004_remove_plaintext_confidential_content.py` | `[('graduate_tracer', '0003_encrypt_confidential_content')]` |
| `be/compass/graduate_tracer/migrations/0005_graduation_classification.py` | `[('graduate_tracer', '0004_remove_plaintext_confidential_content'), ('organization', '0003_program'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/guidance_messages/migrations/0001_initial.py` | `[('appointments', '0003_service_name_snapshot'), ('organization', '0003_program'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/guidance_messages/migrations/0002_guidance_message_template.py` | `[('guidance_messages', '0001_initial'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/institutional_forms/migrations/0001_initial.py` | `[]` |
| `be/compass/institutional_forms/migrations/0002_routine_interview_family.py` | `[('institutional_forms', '0001_initial')]` |
| `be/compass/institutional_forms/migrations/0003_allow_revisions_sharing_schema.py` | `[('institutional_forms', '0002_routine_interview_family')]` |
| `be/compass/institutional_forms/migrations/0004_referral_slip_family.py` | `[('institutional_forms', '0003_allow_revisions_sharing_schema')]` |
| `be/compass/institutional_forms/migrations/0005_call_slip_family.py` | `[('institutional_forms', '0004_referral_slip_family')]` |
| `be/compass/institutional_forms/migrations/0006_good_moral_families.py` | `[('institutional_forms', '0005_call_slip_family')]` |
| `be/compass/institutional_forms/migrations/0007_customer_feedback_family.py` | `[('institutional_forms', '0006_good_moral_families')]` |
| `be/compass/inventory/migrations/0001_initial.py` | `[('institutional_forms', '0001_initial'), ('organization', '0002_academic_year'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/inventory/migrations/0002_inventory_academic_context.py` | `[('organization', '0003_program'), ('inventory', '0001_initial')]` |
| `be/compass/inventory/migrations/0003_inventory_profiling_normalization.py` | `[('inventory', '0002_inventory_academic_context')]` |
| `be/compass/inventory/migrations/0004_student_support_profile_context.py` | `[('inventory', '0003_inventory_profiling_normalization'), ('student_support', '0001_initial')]` |
| `be/compass/inventory/migrations/0005_submission_history_reopen.py` | `[('inventory', '0004_student_support_profile_context'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/inventory/migrations/0006_encrypt_confidential_content.py` | `[('inventory', '0005_submission_history_reopen')]` |
| `be/compass/inventory/migrations/0007_remove_plaintext_confidential_content.py` | `[('inventory', '0006_encrypt_confidential_content')]` |
| `be/compass/inventory/migrations/0008_inventoryreopenevent_targets_ciphertext.py` | `[('inventory', '0007_remove_plaintext_confidential_content')]` |
| `be/compass/notifications/migrations/0001_initial.py` | `[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/notifications/migrations/0002_pushsubscription_pushdelivery_and_more.py` | `[('authentication', '0002_email_change_request'), ('notifications', '0001_initial'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/organization/migrations/0001_initial.py` | `[('accounts', '0001_initial'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/organization/migrations/0002_academic_year.py` | `[('organization', '0001_initial')]` |
| `be/compass/organization/migrations/0003_program.py` | `[('organization', '0002_academic_year')]` |
| `be/compass/platform_ops/migrations/0001_initial.py` | `[]` |
| `be/compass/privacy_governance/migrations/0001_initial.py` | `[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/privacy_governance/migrations/0002_privacynotice_retentionpolicy_and_more.py` | `[('privacy_governance', '0001_initial'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/privacy_governance/migrations/0003_simplify_privacy_governance_scope.py` | `[('privacy_governance', '0002_privacynotice_retentionpolicy_and_more')]` |
| `be/compass/privacy_governance/migrations/0004_remove_retention_policy.py` | `[('privacy_governance', '0003_simplify_privacy_governance_scope')]` |
| `be/compass/privacy_governance/migrations/0005_operationalretentionrule_dispositioncase_and_more.py` | `[('privacy_governance', '0004_remove_retention_policy'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/privacy_governance/migrations/0006_remove_operationalretentionrule_one_active_retention_category_and_more.py` | `[('privacy_governance', '0005_operationalretentionrule_dispositioncase_and_more'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/referrals/migrations/0001_initial.py` | `[migrations.swappable_dependency(settings.AUTH_USER_MODEL), ('institutional_forms', '0004_referral_slip_family')]` |
| `be/compass/referrals/migrations/0002_void_provenance.py` | `[('referrals', '0001_initial'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/referrals/migrations/0003_encrypt_confidential_content.py` | `[('referrals', '0002_void_provenance')]` |
| `be/compass/referrals/migrations/0004_remove_plaintext_confidential_content.py` | `[('referrals', '0003_encrypt_confidential_content')]` |
| `be/compass/resources/migrations/0001_initial.py` | `[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `be/compass/resources/migrations/0002_alter_resource_audience.py` | `[('resources', '0001_initial')]` |
| `be/compass/routine_interviews/migrations/0001_initial.py` | `[migrations.swappable_dependency(settings.AUTH_USER_MODEL), ('appointments', '0001_initial'), ('counseling', '0001_initial'), ('institutional_forms', '0002_routine_interview_family'), ('inventory', '0001_initial')]` |
| `be/compass/routine_interviews/migrations/0002_encrypt_routine_content.py` | `[('routine_interviews', '0001_initial')]` |
| `be/compass/routine_interviews/migrations/0003_remove_plaintext_routine_content.py` | `[('routine_interviews', '0002_encrypt_routine_content')]` |
| `be/compass/routine_interviews/migrations/0004_optional_inventory_and_academic_year.py` | `[('inventory', '0007_remove_plaintext_confidential_content'), ('organization', '0003_program'), ('routine_interviews', '0003_remove_plaintext_routine_content')]` |
| `be/compass/service_catalog/migrations/0001_initial.py` | `[('accounts', '0001_initial')]` |
| `be/compass/service_catalog/migrations/0002_service_cancellation_cutoff.py` | `[('service_catalog', '0001_initial')]` |
| `be/compass/service_catalog/migrations/0003_service_requires_current_inventory.py` | `[('service_catalog', '0002_service_cancellation_cutoff')]` |
| `be/compass/service_catalog/migrations/0004_booking_capability_and_counselor_coverage.py` | `[migrations.swappable_dependency(settings.AUTH_USER_MODEL), ('service_catalog', '0003_service_requires_current_inventory')]` |
| `be/compass/student_support/migrations/0001_initial.py` | `[('inventory', '0003_inventory_profiling_normalization')]` |

## Custom operations and intended empty-database treatment

These are proposed treatments, not authorization to delete history on staging. Every custom operation remains intact until its owning models and consumers are finalized.

| Family | Current purpose | Proposed treatment / proof required |
| --- | --- | --- |
| Identity lifecycle/capability rename | Backfills old users and migrates grants/overrides | Fresh schema fields plus canonical identity sync; prove effective grants for all roles/designations and override behavior. |
| Institutional Forms | Seeds historical form families and revisions | Determine minimum initialization required by saved revisions; use canonical sync for current configuration. Do not assume all seeded identities may disappear. |
| Accounts, Counseling, Referrals, Inventory, Exit Interviews, Feedback, Graduate Tracer, Routine Interviews encryption | Adds ciphertext, backfills, verifies, locks tables, removes plaintext, and provides reverse behavior | Fresh ciphertext-only fields and constraints; preserve envelope version/binding and key rotation; no runtime import from frozen migration schemas was found. |
| Student Support / Inventory | Copies parent-life status and separates support context | Fresh surviving model schema; verify current report/clinical projections. |
| Routine Interview academic year | Backfills year and allows no Inventory | Preserve optional Inventory and explicit academic-year semantics. |
| Appointments/Counseling service snapshots | Backfills provenance/name | Declare current snapshot fields and verify runtime creation paths. |
| E-Counseling media v2, reconciliation, webhook provenance | Moves provider artifacts/consent into new custody model | Preserve consent, source ownership, disposed markers, captures, attempts, callback provenance and indexes; tests must restore the whole graph. |
| Deleted Documents/Privacy models | Refuses deletion if historical rows exist | Empty baseline can omit retired tables once consumers are proven absent; historical evidence/export requires separate operator handling. |
| Call Slip issuance / Good Moral initiation | Marks unknown historical origin | Decide whether unknown-origin enum values remain supported; retain provenance semantics and database defaults until reviewed. |

The source scan found `db_default="LEGACY_UNSPECIFIED"` in Good Moral migration 0006. It must be explicitly compared with current model semantics. No CREATE TRIGGER/FUNCTION/EXTENSION or RunSQL was found by the targeted source scan; custom RunPython SQL still requires review (including table locks).

## Consolidation gates

Do not promise exactly one initial migration per app: Django may need additional baseline migrations to break cross-app FK cycles. In particular, the historical Inventory / Student Support graph interleaves migrations. Preserve swappable user dependencies and the final constraints/indexes rather than concatenating operations.

The reviewed ordinary deployment order is `migrate → sync_identity_policy → sync_canonical_services → sync_institutional_forms → sync_organization_catalog → check --deploy`. Rehearse this order against the finalized empty baseline; startup defaults must not replace explicit configuration synchronization.

Replacement history belongs only on `canon/compass-clean-baseline`, created after compatible prerequisites are reviewed. Ordinary deployment currently applies migrations before replacing workers; it cannot be reused for a reset-only release. Never use --fake-initial to conceal an incompatible old database.

Required later evidence: A existing-history database/schema; B canonical database/schema and explained differences; C fresh install, sync, checks, workflow creation, seeding and reports; D rerun/idempotency; E ciphertext/FK/uniqueness/index/provenance invariants. No canonical baseline or schema-equivalence result exists yet.
