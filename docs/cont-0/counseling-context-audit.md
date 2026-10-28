# Existing Counseling Context

Evidence: [context_access.py](../../be/compass/counseling/context_access.py), [context_services.py](../../be/compass/counseling/context_services.py), [context_api.py](../../be/compass/counseling/context_api.py), [matching.py](../../be/compass/routine_interviews/matching.py), [settings](../../be/config/settings.py), [existing tests](../../be/tests/test_counseling_context.py). This is current behavior, not a proposed grant.

## Activation and expiry

Both anchors require a saved active `COUNSELOR` with effective `counseling.view_assigned` at evaluation time. The route returns 403 for an ineligible actor; a missing/out-of-scope/expired anchor is concealed as `404 counseling_context_not_found`. Unsupported anchors fail closed. `counseling_context_available` is advisory: opening each endpoint resolves again.

| Anchor | Activates | Base expiry | Matching completed Encounter extension |
| --- | --- | --- | --- |
| `APPOINTMENT` | Canonical Counseling Service; exact `provider_id == actor.pk`; status SCHEDULED or COMPLETED; `starts_at - 24h` | `ends_at + 24h` | `encounter.ended_at + 7 days`, replacing base expiry |
| `ROUTINE_INTERVIEW` | Exact `counselor_id == actor.pk`; **no Appointment**; WALK_IN, CALLED_IN or REFERRED; Intake submitted; `intake_submitted_at` | Submission + 24h | Matching Encounter end + 7 days, replacing base expiry |

Settings default to `COUNSELING_CONTEXT_PRE_APPOINTMENT_HOURS=24`, `COUNSELING_CONTEXT_UNCOMPLETED_GRACE_HOURS=24`, `COUNSELING_CONTEXT_POST_ENCOUNTER_DAYS=7`. Startup permits 0–168 hours and 0–30 days respectively. This audit proposes **no change** to these defaults or bounds.

Current comparison rejects `now < valid_from` or `now > valid_until`; the exact endpoint is inclusive. A future grant's half-open interval is its own contract and must not silently alter Context.

Appointment matching verifies Appointment FK, Student, provider/Counselor, canonical Service code, APPOINTMENT entry mode, matching delivery, completed end (`<= now`), end not earlier than pre-window start, and start not later than base expiry. Rows sort by end/ID and the first matching row is used. The unique Appointment relationship normally leaves at most one candidate.

Direct matching first checks the persisted Encounter link. It requires end after activation, start before base expiry, matching Student/Counselor/Service/delivery/entry mode, no Appointment, and end not in future. A bad persisted link is authoritative as a **failed extension**; the resolver does not substitute another Encounter. If unlinked, at most the first five eligible unlinked Encounters (end/ID order, no other Routine link) are considered. A matching candidate extends access but is not persisted as a new relationship. There is no arbitrary future Encounter extension; unusually long actual Encounters can extend if these predicates hold.

## Invalidation and questions answered

| Question | Verified answer |
| --- | --- |
| What activates/ends access? | The anchor predicates and calculated interval above, evaluated against backend time per request; no stored grant or expiry job. |
| Immediate invalidation? | Actor inactivity, role/capability loss; wrong assigned provider/Counselor; Appointment CANCELLED/NO_SHOW or non-Counseling Service; direct Intake no longer submitted/entry invalid/Appointment attached; current time outside recalculated window. Cancelling an Appointment invalidates even an otherwise extended Context. |
| Does completion invalidate? | COMPLETED Appointment remains eligible. A matching completed Encounter establishes the seven-day calculation. Routine Evaluation finalization is not a separate revocation condition. |
| College-responsible Counselor required? | No. Exact assigned provider/direct Counselor matters. Changing Student College does not by itself invalidate a still qualifying Context. |
| Does Head designation grant access? | No. Head must be exact provider/direct Counselor and meet ordinary role/capability/window checks. GSS supervision never inherits the relation. |
| Stale/incorrect source records? | Old anchors expire unless a qualifying extension applies. Wrong Student/Counselor/Service/mode/Appointment or future-ended Encounter cannot extend. A submitted direct anchor can still have its base window even with no valid extension; the bad Encounter does not create the base authority. |
| Is the Student's current active status checked here? | The resolver checks actor activity, not a distinct current Student active/role requirement for every anchor. Writers validate participants, but do not claim current Student deactivation is a Context revocation predicate. Future continuity should explicitly decide and check subject eligibility. |
| Is Service provider eligibility rechecked? | Exact saved relationship and canonical Service code are checked. Current College responsibility/current Service provider coverage are not additional resolver checks. New scheduling/creation has separate eligibility rules. |
| After expiry? | All Context sections deny; own Encounter detail, own assigned Routine detail and own authored Summary remain governed by their independent routes and capabilities. Student self access is independent. |
| Can a Context be reused later? | Low-level projection functions trust `CounselingContextAccess`; they do not re-resolve or check expiry. Current API calls resolve immediately. Do not persist/pass this dataclass as durable authorization or fabricate it for continuity. |

## Projections and sensitivity

| Projection / operation | Actual output and cross-author scope | Exclusions / limitation |
| --- | --- | --- |
| `counselingContextGetOverview` | Student ID/institutional ID/name/photo, current College/Campus, Inventory Program/year, anchor/window, anchor Routine statuses, matching/linked Encounter ID and times | No Intake/Evaluation body. If current Academic Year is missing, optional enrichment can be absent. |
| `counselingContextGetInventory` | Full `CounselorInventoryDetailResponse` from submitted Routine-bound Inventory, otherwise submitted current Inventory. Can cross College and original interaction authorship. | Bound Inventory's current submission state applies; reopened draft is hidden. Unbound Routine stays unbound; fallback does not rewrite provenance. It is **not a metadata-only endpoint**. |
| `counselingContextGetSupportIndicators` | Current Academic Year submitted Inventory factual support indicators, independent of older Routine-bound Inventory | No raw professional Evaluation. Current-year configuration errors return scoped conflict. Indicator labels still convey sensitive circumstances. |
| `counselingContextListHistory` | All-Student Appointment, Referral, Call Slip, Routine metadata, including other providers: UUID/kind/time/title/status/reference/delivery/provider | No historical Encounter list, reason/narrative/Intake/Evaluation/media. Each category bounded to requested limit, merged descending and finally bounded (1–50, default 20). Metadata does not authorize destination detail. |
| `counselingContextListSharedSummaries` | Student's published Summary bodies, author identity, publication and Encounter end; **all authors**; latest 1–50 | Excludes drafts/other Students. Decrypts after Student/publication selection, but without author or `shared_summaries.view_assigned` check. CONT-F01. |

## Cross-College proof and coverage

`world` in `test_counseling_context.py` assigns the Student to CAS, Counselor A to CAS, and Counselor B to CCMS. `test_appointment_context_is_exact_provider_time_bounded_and_cancel_revokes` grants B access as exact provider and denies A, Head and unrelated Counselor. `test_contextual_inventory_and_support_do_not_weaken_generic_authorization` expects Context Inventory/Support HTTP 200 for B while the generic Inventory/Support routes return 404. `test_head_has_context_only_when_head_is_exact_appointment_provider` checks Head identity. `test_appointment_completed_encounter_extends_context_but_own_record_survives_expiry` checks independent historical ownership. These are inspected source expectations, not executed database proof in CONT-0.

`test_matching_direct_encounter_extends_context_and_mismatch_does_not` covers the three direct entry modes and mismatch behavior. Linking tests in `test_routine_encounter_linking.py` cover deterministic provenance. `test_context_history_is_minimized_and_private_encounters_stay_hidden` and `test_context_shared_summaries_are_published_only` cover projection boundaries; the latter explicitly creates A's published Summary and lets B read it.

## Gaps and reuse decision

CONT-F08: overview prefers `routine.counseling_encounter` whenever persisted, without calling the matching predicate. `_routine_interview` checks Student but not exact Counselor; the Appointment resolver initially discovers a Routine by Appointment FK. Normal creation/linking services validate these identities, and no arbitrary linking API was shown to bypass them. Add a narrowly scoped malformed-link regression and projection validation before trusting imported/corrupt persisted relationships; do not call this a confirmed exploitable endpoint bypass.

The frontend [workspace](../../fe/src/features/counseling/counseling-workspace.tsx) uses `valid_until`, server response date and `useServerBoundary`, clears Context section query keys on expiry, and hides on authority/Context-not-found errors. This is useful existing UX, not server authorization or a guarantee that a revoked remote actor's already rendered page disappears instantly. Section changes still call the resolver. The [service worker](../../fe/public/sw.js) caches only the generic offline page, not authenticated API content. No dedicated no-store header was found on the inspected Counseling/Context responses; verify end-to-end proxy/browser behavior in CONT-4.

Preserve this resolver and its legitimate access. For continuity, reuse only reviewed pure serializers/builders **after a separate continuity decision**. Do not call `get_context_inventory`, `list_context_history` or the overview wholesale: each has broader source selection than an explicit continuity scope. Remove Context Shared Summaries in CONT-1A; never replace it with automatic handoff readership.
