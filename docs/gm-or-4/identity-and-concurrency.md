# Identity and coordination evidence

GM_OR_V1 rejects nonprintable/non-ASCII before trimming, trims only ordinary outer spaces, uppercases ASCII for a global C-collated key and preserves trimmed display. Leading zeroes, prefixes, punctuation and internal spaces remain significant. Maximum display/key length is 96; empty normalization cannot reserve an identity. Blank correction is an explicit absence revision. No Student/year/variant/status scope is added. Canonical identity tests cover accepted boundaries and invalid types/characters. Unsupported legacy observations remain exact quarantined facts.

Permanent reservation proof reruns A→B→clear/replacement→cancel and rejects both old and terminal-number reuse, including same-request reactivation. Amount/date-only corrections append under the same binding. New actual-browser replacement retains the old key and invalidated personal inspection. New cross-variant replacement/reuse coordination checks committed rows and Audit.

## Direct PostgreSQL bypass inventory

`test_database_guards_reject_alternative_writers`, `test_database_claim_and_identity_shapes`, `test_unclaimed_ordinary_reservation_cannot_commit`, `test_new_operation_rows_must_reference_the_current_result`, `test_direct_database_rewrite_and_reference_bypass_refused`, and `test_direct_insert_inspection_guards` reject rekey/delete/fact rewriting, invalid predecessor/owner, dual-current claims, projection tampering, old-key restoration, invalid evidence references, original attestation changes and illegal mode/terminal downgrades. Tests commit/defer constraints on real PostgreSQL. Named uniqueness/check constraints and installed triggers remain the authority; no new test disables a guard to make a bypass pass.

The retained prior identity-eligibility tests include explicitly privileged fixture construction of otherwise impossible future disputed/wrong-owner states. Those setup operations are not counted as ordinary-writer guard proof. They are separate from the direct guards and do not authorize disabling production guards. A database owner or infrastructure administrator can bypass/drop guards or restore incomplete data; ordinary SQL protection is not protection from that privilege.

## Requested 25-item matrix

Both actual coordination and transaction fault tests are labeled explicitly. Case counts refer to distinct parameterized nodes, not repeated runs. The count of independent-connection cases is recorded in validation/evidence. Fresh distributed policy-writer/privileged administrative coordination is not invented.

| # | Requested case | Test stems | Actual evidence / limitation | Verdict |
| --- | --- | --- | --- | --- |
| 1 | Concurrent same OR | same_absent_key[False] | Independent connections + barrier; one identity/claim winner, loser no orphan | PASS |
| 2 | F4 versus F6 collision | same_absent_key[True] | Same global uniqueness arbiter; no variant scope | PASS |
| 3 | Same-request corrections | same_request_edits_and_replays + simultaneous_replacement | Independent connections; stale loser, one revision chain | PASS |
| 4 | Replacement versus old-number reuse | new replacement_racing_old_number_reuse | Barrier; replacement commits, reuse conflicts, old/new reservations retained, two correction Audit events only | PASS |
| 5 | Correction versus verification | inspection_competes[correction] both orders | Request fence + exact version; final rows/Audit asserted | PASS |
| 6 | Verification versus preparation | inspection_competes[prepare] both orders | Reviewed request token prevents stale prepare; no invented inspection | PASS |
| 7 | Verification versus issuance | inspection_competes[issue] both orders | Exact committed inspection replay competes with issue; not two fresh independent eligible inspections | PARTIAL |
| 8 | Correction versus issuance | final_issue_and_late_correction + lifecycle_competition[issue] | Both orders; terminal/stale outcome preserves single history | PASS |
| 9 | Cancellation versus verification | inspection_competes[cancel] both orders | Terminal state, invalidation and reservations retained | PASS |
| 10 | Cancellation versus preparation | new cancellation_and_preparation both orders | Two connections; CANCELLED final, stale preparation denied, one cancellation Audit | PASS |
| 11 | Two verification attempts | simultaneous_inspection[False] | Barrier and unique active attestation; one original attribution | PASS |
| 12 | Identical inspection replay | simultaneous_inspection[True] | Single operation/evidence/Audit | PASS |
| 13 | Conflicting operation UUID | concurrent_global_operation_reuse + receipt concurrent_operation_uuid | Independent request transactions, loser rollback | PASS |
| 14 | Revocation during inspection | account_change before/after fence[revocation] | Supported User-lock administration serializes both orders | PASS |
| 15 | Deactivation during inspection | account_change before/after fence[deactivation] | Supported User-lock administration; final authority recheck | PASS |
| 16 | Fee loss during verification | policy_changes_during_transaction[verify] | Real PG transaction + injected provider fault; no independent distributed policy writer | PARTIAL |
| 17 | Fee loss between prepare/issue | policy_change_before_issue and transaction[issue] | Real persistence/gate failure and rollback; provider injected | PARTIAL |
| 18 | Writer fence versus receipt mutation | fence_waits_for_old_writer | Shared/exclusive PG fence drains old writer and captures committed projection | PASS |
| 19 | Writer fence versus verification | inspection_waits_for_real_dormant_to_fenced_transition | Independent connections; verification denied behind committed fence | PASS |
| 20 | Import versus conflicting assignment | active_assignment_and_import_never_form_dual_writer_interval | Real connections prove active/import exclusion; not a separate simultaneous same-key import insertion race | PARTIAL |
| 21 | Audit failure during correction | audit_failure_rolls_back_all_receipt_facts | Synchronous injected failure with real PG rollback; not a concurrency schedule | PASS |
| 22 | Audit failure during verification | audit_failure_rolls_back_attestation[verification] | Synchronous injected failure; no committed evidence/Audit | PASS |
| 23 | Notification/feedback failure during issuance | new outcome_failure[feedback/issuance-notification/invitation] | Three transaction failures then explicit retry/replay; no duplicate outcomes | PASS |
| 24 | Lock timeout and recovery | receipt_lock_timeout | Independent holder/contender, short DB lock timeout, deliberate recovery | PASS |
| 25 | Repeated successful issuance | full_workflow_and_issued_replay + new API full workflow | Committed replay leaves all facts/outcomes unchanged; sequential idempotency, not another race | PASS |

## Stale final review and lock order

The request is the serial fence. Receipt-control shared lock coordinates cutover; identity precedes claim/inspection locks; supported actor-account changes share identity locks. F4 final issuance orders actor and Student User locks consistently and rechecks CURRENT. Receipt correction, current inspection, preparation/request version and final reviewed evidence must match. An exact old committed replay may acknowledge evidence but cannot restore current eligibility. No client automatically retries stale consequential mutations.

Policy-loss fault injection uses actual PostgreSQL rollback with a code-owned resolver seam, not mocked database coordination. Uncontrolled privileged account-policy edits and mixed-process fee definitions need a release/writer-drain protocol; these tests do not establish serializability for them.
