# Dataset v2 pre-deployment implementation report

Validation date: 2026-10-08. PR: [#192](https://github.com/ils12058/COMPASS/pull/192).
This report concerns local validation, completed full-suite CI and repository changes. No live database was seeded.

1. **Starting staging SHA:** `b343f8419dc9bf58d83fe20779695a784df65156`, fetched before
   implementation; `feat: persistent E-Counseling call across the portal (ADR-094) (#191)`.
2. **Resulting branch/head:** `codex/demo-dataset-v2`; the validated implementation commit is
   `afdad7ba9744f77725838fcf1bc970be48f3c4f9`. The final handoff records the subsequent report-only
   commit SHA. Worktree: `/Users/reynantlntno/.codex/worktrees/demo-dataset-v2/COMPASS`.
3. **ADR:** [ADR-095 — Staging demo dataset v2 and pre-deployment validation baseline](decisions/ADR-095-staging-demo-dataset-v2-and-pre-deployment-validation-baseline.md).
   ADR-068 remains historical; decisions through ADR-094 remain in force.
4. **Original baseline:** an immutable archive of the fetched staging SHA reproduced **12 failed,
   2925 passed, 17 errors, 17 warnings**, in **3011.57 seconds**. The failing/error nodes match the
   latest completed backend CI failure set, run
   [37708580157](https://github.com/ils12058/COMPASS/actions/runs/37708580157), whose head was
   `0ac4dcec9368aec0705ae9f74a4df9fe6e36101b`: the same totals, in 4300.52 seconds.
   PostgreSQL 17 and Redis 8 were dedicated local test containers. An initial focused login
   failure caused by unavailable local Redis disappeared when Redis was supplied; it was not
   treated as a product regression or suppressed.
5. **Resolved failing/error nodes:** see the root-cause inventory below. No skips/xfails were added.
6. **Production defects:** demo bookings assumed a fixed interval despite current institutional
   Availability; bounded ordinary slot discovery now places them legally. Three Appointment
   cancellation/completion/no-show queries joined Service while taking unscoped row locks;
   `select_for_update(of=("self",))` now declares Appointment row ownership. The static invariant
   was left unchanged. A two-day institutional closure also reproduced Feedback/follow-up dates
   preceding the discovered session; newly created Feedback and follow-up bookings now follow the
   actual completed Encounter. Existing history is preserved. The remaining seeder changes add
   v2 content and safeguards.
7. **Stale tests:** action projection now includes linked E-Counseling blockers and consequences;
   authenticated Student responses deliberately expose Exit Interview workspace eligibility;
   Feedback prose is read through its encrypted boundary; canonical Counseling cannot be
   disabled under ADR-089; errors use the canonical nested envelope; Organization responsibility
   scope is a closed nullable enum; disclosure-suppressed report percentages are nullable; Tracer
   reports expose disclosure warnings. Assertions retain these deliberate contracts and closed
   typed errors. Dataset counts change only where the declared v2 fixture expands composition.
8. **Final full pytest:** **2983 passed, 0 failed, 0 errors, 17 warnings in 3969.41 seconds
   (1:06:09)**, from the complete `uv run pytest tests` CI execution on
   `afdad7ba9744f77725838fcf1bc970be48f3c4f9` in
   [run 37724845303](https://github.com/ils12058/COMPASS/actions/runs/37724845303).
   The workflow checks out the exact PR head. All job steps succeeded, including static,
   migration and contract checks. It completed on 2026-10-08 at 13:00 Manila time.
   The duplicate local final run was still incomplete when CI success was verified and was
   stopped to release resources. It is not presented as a completed local full-suite result.
9. **V1 → v2 upgrade:** additive provisioning with stable original identities, markers, natural
   keys and legacy `demo-seed-v1` idempotency keys. Existing records and credentials are reused.
   Original v1 history remains the completeness boundary; new population history is entered per
   Student in bounded transactions through owning services. Each transaction restores the current
   Academic Year before commit. Established graduates are never returned to CURRENT to manufacture
   missing history. Identity/name and academic provenance conflicts fail closed.
10. **Student count:** 57 Students and 7 staff accounts, 64 accounts total.
11. **Lifecycle:** 46 CURRENT, 8 GRADUATED, 3 FORMER. Onboarding and disabled historical staff
    examples survive. Graduates/former Students are excluded from current affiliation rosters.
12. **Catalog/year distribution:** enrollment-origin Colleges are CCMS 15, CAS 16, CBPA 14,
    COED 12. Actual CURRENT affiliations are CCMS 13, CAS 12, CBPA 12, COED 9; Counselor A routes
    25 and Counselor B 21. All Program codes come from the synchronized canonical catalog.
    Program-origin and current Inventory distributions are recorded in the table below.
    Current Inventory year levels are 1:9, 2:11, 3:11, 4:10, 5:1. The four missing Inventories have
    no authoritative Inventory Program/year for reporting; affiliation still supplies College.
13. **Rich personas:** the original eleven retain their names, identities and cross-domain stories:
    Abad, Serrano, Dela Paz, Pardo, Obusan, Rosales, Cabrera, Samonte, Llamas, Bernardo, Alcantara.
    No additional large rich scenario is invented.
14. **Population cohort:** 46 explicit, stable Students: 38 CURRENT, 6 graduates, 2 former.
    Identity, Inventory answer fixtures, other form answers, and orchestration are separate modules.
    Eight Students have one lightweight Appointment; two have compact Routine stories. Most have
    account/profile/affiliation/Inventory only. There is no runtime Faker population generation.
15. **Inventory coverage:** 67 annual records: 6 in 2024-2025, 19 in 2025-2026, 42 in current
    2026-2027. History includes selected older-year CURRENT Students and graduated/former cohorts.
16. **Current Inventory states:** 34 submitted (73.91% of 46), 8 draft (17.39%), 4 missing (8.70%).
    Population drafts include two early, two partial and three nearly complete; the original
    active-referral Student retains a draft. Submission uses the normal owning service.
17. **Inventory children:** clean-seed aggregates are 124 family members, 149 sibling rows
    (including self rows), 186 education entries, 43 organization memberships and 64 transport
    entries. Complete, only-child, multi-sibling, early draft and partial draft shapes differ.
    Education dates are related to admission year; coded values use the current instrument.
18. **Support variety:** ordinary submissions outnumber support-indicator submissions. Derived
    indicators cover PWD, 4Ps beneficiary, Indigenous Peoples membership and deceased father.
    Additional form variety covers working Students, single-income/guardian households, long
    commutes, organizations and ordinary/no-major-concern narratives. Support is derived normally.
19. **Routine coverage:** 6 Routines: 1 draft Intake, 5 submitted Intakes; Appointment-backed,
    referred and direct/walk-in entries with deterministic Encounter links. `population_38` has
    submitted Intake and a linked Encounter with no Inventory, preserving ADR-088.
20. **Evaluation coverage:** 3 finalized, 2 pending after submitted Intake; the remaining draft
    Intake has no final evaluation. Career planning and elective planning add different narratives
    and ratings to the original adjustment/referred/walk-in scenarios.
21. **Counseling/Summaries:** 7 Encounters: 3 Appointment-backed, 3 WALK_IN, 1 REFERRED. Three
    Shared Summaries: 2 published, 1 draft; four Encounters legitimately have none. Appointment-backed
    intervals fit the selected booking; recorded/finalized timestamps follow the encounter.
22. **Appointments:** 16: 8 scheduled, 3 completed, 3 cancelled, 2 no-show. Modes: 13 IN_PERSON,
    3 ONLINE; all ONLINE examples are scheduled. Most Students have no Appointment. ONLINE state
    supports the ordinary lazy E-Counseling workspace without provider objects/media.
23. **Slot algorithm:** ordinary `list_bookable_slots` checks current Service configuration,
    duration, Inventory prerequisite, selected-provider qualification, office/provider windows,
    exceptions and reservations. Search covers the intended day plus four calendar days, excluding
    weekends, demo non-working days and the anchor, keeping the original past/future side. The
    first viable day wins; nearest desired local start then earlier start breaks ties. Creation
    remains ordinary `create_student_appointment`; terminal, Encounter, Feedback and follow-up
    booking times follow the result.
24. **Compatible Availability:** a focused test supplies 11:00–16:00 institutional office and
    Counselor A windows and a two-day institutional office closure that moves the initial session.
    Every supplied window/exception row remains byte-for-byte unchanged; all booked intervals lie
    within actual base windows. Feedback follows service completion and follow-up creation follows
    the selected completed interval. Empty schedules alone receive the existing demo defaults.
25. **Incompatible Availability:** 08:00–08:30 office windows fail the first unsatisfiable scenario
    with scenario/Student/provider/mode/search-window context. Existing windows remain unchanged;
    that scenario creates no Appointment. Search does not overwrite schedules or loop indefinitely.
26. **Exit coverage:** 13: 10 submitted, 3 draft; eligible remaining Students are not started.
    Early and substantially complete drafts coexist. Submitted/detailed matrices use varied 3/4/5
    ratings and real item codes. Historical forms are entered while legitimately enrolled through
    the normal Exit service, before graduate transitions.
27. **Tracer coverage:** 8 graduates: 6 submitted responses, 1 draft, 1 not started. Paths include
    course-related and unrelated employment, self-employment, job-seeking and further study/training;
    first-job timelines, sectors, competencies and training entries differ. Normal validation and
    confidential-content services own the responses.
28. **Good Moral:** 5 requests: 2 issued, 2 requested, 1 cancelled. Current issuance/cancellation,
    graduating pending with Exit prerequisite, graduate pending and graduate issued are preserved.
    Certificates remain renderable through the current controlled-document context.
29. **Referral/Call Slip:** 4 Referrals, including active, completed/historical and voided duplicate;
    4 Call Slips (1 voided, 2 completed), including direct/referral provenance, former staff
    authorship and future reporting. Confidential reasons/action remarks use encrypted services.
30. **Account Profile:** real current fields include date of birth, civil status, distinct synthetic
    addresses, and optional synthetic contact labels for a subset. Existing Profiles are not
    rewritten. Onboarding still demonstrates the first-password path and established passwords
    survive upgrades/reruns.
31. **Feedback/CSM:** 6 each, with different 3/4/5 patterns; 5 have written text, 1 leaves optional
    prose empty. Two new secondary Encounter opportunities complement original legitimate sources.
    Opportunity reconciliation prevents raw-response recreation; encrypted logical reads are used.
32. **Encryption tests:** SQL persisted-row checks and supported logical/API reads cover Account
    Profile, Feedback/CSM, Shared Summary, Referral/action remarks, Inventory/root and confidential
    family/education children, Exit and Tracer. Existing Routine tests independently check the
    encrypted Intake/Evaluation columns and round trips. Known selected prose is absent from raw
    rows; failures do not dump entire decrypted records. No plaintext model field is reintroduced.
    The complete Feedback encryption module passes all 79 tests after isolating its single-persona
    unit fixture from both source-controlled demo cohorts; corrupt-content propagation remains tested.
33. **Keyring preflight:** all eight owning settings are encrypt/decrypt probed before canonical
    synchronization/account writes. Sixteen missing/invalid cases verify zero User/Audit writes.
    Settings: Account Profile, Feedback, Routine, Shared Summary, Referral, Exit, Inventory, Tracer.
    Errors print the setting name, not key/token/payload. No seeder key generation or recovery exists.
34. **External calls:** seeder tests forbid Daily, PSGC, Playwright PDF rendering, storage save,
    Mailer send, urllib HTTP and requests HTTP. Unexpected calls fail the test. Runtime-only
    E-Counseling media/provider state, resource files and structured PSGC are intentionally absent.
35. **Email:** legitimate Notifications remain; only seed-caused, never-attempted delivery intents
    are settled/removed before bounded commits. Exercised on-commit delivery tasks return skipped,
    Mailer is never invoked, and pending demo emails are zero. Runtime delivery behavior is intact.
    Clean aggregate audit observed 56 Notifications, 53 unread; quiet population examples have none.
36. **Idempotency:** two actual clean-seed executions in the same local test process produced
    identical aggregate counts, child counts, account states, password hashes and Audit counts.
    The second report created zero logical records. The unchanged PostgreSQL advisory lock guards
    concurrent runs. Interrupted population-unit recovery and subsequent idempotency also pass.
37. **Upgrade test:** a v1 cohort reconstructed with today's owning services is upgraded to v2.
    Snapshots of all original Inventory, Appointment, Routine, Exit, Tracer, Summary, Referral and
    Feedback rows remain exactly equal. A deliberately changed password survives; the second v2
    execution creates nothing. This is local model/service validation, not an assertion about a
    live database that was never inspected or modified.
38. **API smokes:** actual local seeded head-guidance requests to `/api/v1/overview`,
    `/api/v1/inventory/students`, `/api/v1/reports/student-profile`, `/api/v1/reports/graduate-tracer`,
    `/api/v1/routine-interviews`, `/api/v1/appointments` all return 200. Test coverage also includes
    Student session/Profile/current Inventory, authorized Feedback detail, normal document
    projections, pagination (default 20), name search, College/Program/year/status filters,
    ascending/descending sort and both Counselor scopes. Anchors 2026-09-21, 2026-10-08 and
    2027-04-30 seed valid intervals.
39. **OpenAPI:** export and `--check` pass; the committed canonical contract has no diff. Tests now
    explicitly retain the closed nullable responsibility enum and nullable numeric disclosure values.
40. **Migrations/Django:** `makemigrations --check --dry-run` reports no changes; all migrations
    apply to a fresh dedicated local database; `check` reports zero issues. No migration was added.
41. **Static checks:** `uv lock --check`, Ruff format, Ruff lint, compileall for
    `compass tests`, and `git diff --check` pass. Locked dependencies are unchanged.
42. **Frontend:** no feature or contract changes. Orval regeneration and frontend tests/build are
    not applicable; generated frontend files are unchanged.
43. **Runtime impact:** the final full CI run took **3969.41 seconds**, compared with the previous
    failed CI baseline's 4300.52 seconds: 331.11 seconds (7.70%) shorter despite 29 additional
    tests (2954 → 2983). This is an observed run comparison, not a controlled performance claim;
    the baseline failed and runner conditions can differ. The local untouched baseline took
    3011.57 seconds; there is no completed final local run for a same-environment comparison.
    Read-only v2 checks share one clean seed; cohort Students mostly avoid
    expensive transactional histories. Focused checks cover the expensive independent upgrade,
    schedule, anchor and recovery paths. The final complete demo-seeder recheck reports **78 passed
    in 480.79 seconds**, with no failures/errors/warnings.
44. **Warnings:** the final pytest run retains **17 existing warnings**: six Django Ninja
    tuple-response deprecations, ten pypdf content-replacement deprecations and one Django warning
    for a deliberate DATABASES override in an environment-projection test. These match the
    baseline categories/counts and were reviewed without suppression. GitHub Action tooling also
    emits Node `punycode` and `url.parse` deprecation messages outside the pytest warning count.
45. **Scope confirmation:** no live deployment, live seeding, secret provisioning/rotation, Daily
    provisioning, Spaces mutation or confidential-content encryption cutover occurred. No merge
    was performed. Retention/disposition/consent/media architecture remain unchanged. Local tests
    use existing test-settings ephemeral keyrings and dedicated PostgreSQL/Redis resources.

## Root-cause inventory of the untouched baseline

All paths below are relative to `be/tests/`.

| Root cause | Failed nodes | Setup errors | Resolution |
| --- | ---: | ---: | --- |
| Fixed demo Appointment interval contradicts Availability | 3 | 17 | Bounded ordinary slot discovery; preserve institutional windows |
| Joined Appointment locks lack declared ownership | 1 | 0 | Three production queries scope locks to Appointment rows |
| Stale Appointment action projection | 2 | 0 | Linked-room blockers/consequences match current mutations |
| Stale authenticated Student contract | 1 | 0 | Include deliberate Exit workspace eligibility |
| Removed plaintext Feedback model field | 1 | 0 | Supported encrypted logical read |
| Stale canonical-Service and error-envelope assumptions | 2 | 0 | Preserve ADR-089 and current nested error envelope |
| Stale typed OpenAPI assertions | 2 | 0 | Current enum, disclosure nullability and warnings; errors remain typed |

Failed nodes:

```text
test_appointment_action_projection.py::test_manager_actions_follow_server_time_and_linked_records
test_appointment_action_projection.py::test_detail_api_returns_actions_for_the_requesting_actor_only
test_authentication.py::test_authenticated_student_contract_exposes_effective_capabilities_without_scope_leaks
test_counseling_downstream_lifecycle.py::test_submitted_feedback_survives_valid_completion_reconciliation_without_new_invitation
test_cross_domain_lifecycle_reconciliation.py::test_action_projection_matches_mutations_and_room_is_hard_cancellation_blocker
test_cross_domain_lifecycle_reconciliation.py::test_cancelled_appointment_preserves_routine_content_and_blocks_every_mutation_path
test_demo_seed.py::test_live_staging_with_opt_in_seeds_using_the_configured_domain
test_demo_seed.py::test_clean_seed_credentials_auth_state_and_secret_hygiene
test_demo_seed.py::test_seeding_makes_no_external_calls_and_sends_no_email
test_lock_scope.py::test_every_locking_query_that_joins_related_rows_declares_its_lock_scope
test_openapi_contract.py::test_organization_person_projection_schema_is_dedicated_and_complete
test_openapi_contract.py::test_core_schemas_and_realistic_error_responses_are_typed
```

The 17 setup errors all arise from
`SCENARIO_COMPLETED_COUNSELING → AppointmentTimeUnavailable → full interval outside Availability`:

```text
test_demo_seed.py::test_onboarding_persona_resolves_to_the_real_first_password_flow
test_demo_seed.py::SeededDemoDatasetTests::test_academic_years_and_cohort_histories_are_coherent
test_demo_seed.py::SeededDemoDatasetTests::test_appointments_counseling_and_shared_summaries_cover_real_lifecycles
test_demo_seed.py::SeededDemoDatasetTests::test_audit_trail_is_legitimate_attributable_and_secret_free
test_demo_seed.py::SeededDemoDatasetTests::test_configuration_relationships_and_availability
test_demo_seed.py::SeededDemoDatasetTests::test_derived_projections_are_useful_without_being_seeded_directly
test_demo_seed.py::SeededDemoDatasetTests::test_good_moral_exit_interview_tracer_and_feedback
test_demo_seed.py::SeededDemoDatasetTests::test_graduates_and_former_students_are_never_current_classmates
test_demo_seed.py::SeededDemoDatasetTests::test_publications_and_privacy_governance
test_demo_seed.py::SeededDemoDatasetTests::test_referrals_and_call_slips_form_believable_workflows
test_demo_seed.py::SeededDemoDatasetTests::test_roles_designations_lifecycle_and_account_state_are_independent
test_demo_seed.py::SeededDemoDatasetTests::test_routine_content_is_written_through_the_encrypted_boundary
test_demo_seed.py::SeededDemoDatasetTests::test_routine_interviews_cover_draft_submitted_and_finalized_states
test_demo_seed.py::SeededDemoDatasetTests::test_seeded_records_are_readable_through_the_normal_api
test_demo_seed.py::test_ordinary_rerun_is_idempotent_and_preserves_established_credentials
test_demo_seed.py::test_feedback_opportunities_reconcile_known_demo_sources_without_recreating_raw_responses
test_demo_seed.py::test_changing_the_demo_domain_between_runs_fails_closed
```

## Source-controlled catalog distribution

Origin describes the declared cohort Program, including alumni/former Students; current Inventory
counts describe actual current annual records, including drafts. Missing Inventory rows supply no
Program/year report provenance.

| Program | All Student origins | Current Inventory records |
| --- | ---: | ---: |
| BAELS | 1 | 1 |
| BEED | 5 | 4 |
| BSA | 6 | 5 |
| BSBA | 7 | 6 |
| BSBIOL | 7 | 4 |
| BSDEVCOM | 1 | 0 |
| BSED | 7 | 4 |
| BSHM | 1 | 1 |
| BSIS | 7 | 5 |
| BSIT | 8 | 6 |
| BSPSYCH | 7 | 6 |
| Total | 57 | 42 |

## Validation evidence

Local retained logs: `/tmp/compass-v2-baseline.log`, `/tmp/compass-v2-ci-baseline.log`,
`/tmp/compass-v2-final.log` (incomplete duplicate local run),
`/tmp/compass-v2-ci-final.log` (completed exact-head full suite), `/tmp/compass-v2-demo-tests.log`,
`/tmp/compass-v2-demo-recheck.log`, `/tmp/compass-v2-recovery-tests.log`,
`/tmp/compass-v2-all-demo-final.log`, `/tmp/compass-v2-aggregate-audit.json`,
`/tmp/compass-v2-migrate-final.log`.
These temporary files are execution evidence; this source-controlled report records the results.
Intermediate expanded focused runs exposed and corrected test fixture/expectation mistakes before
the final full suite; their partial results are not substituted for full-suite acceptance.
An earlier full attempt stopped after 505 passing tests and one stale Feedback reuse-count assertion
(v1's four versus v2's six). Preserved raw response IDs and opportunity counts were already correct;
the assertion now compares the reuse report to the actual preserved response IDs. A subsequent
partial run was replaced when the institutional-closure chronology regression was reproduced and
fixed. The final complete run is on the final implementation, not an aggregation of partial runs.
Another interrupted run had 1103 passing tests and one isolated Feedback counter test whose mocked
single-persona map omitted the newly added population fixture keys. Both cohort fixtures are now
isolated consistently in that unit; actual combined v2 counts remain covered end-to-end. Storage
assertions expose only boolean verdicts if they fail, avoiding persisted-row/payload dumps.
