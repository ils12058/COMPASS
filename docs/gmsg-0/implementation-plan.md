# GMSG-0 — Migration strategy and the GMSG-1 foundation plan

Design only. No migration, model, policy, contract, seed or test file was created or modified in
GMSG-0; every path below is a **proposal for a later slice**.

## 1. Three options for representing non-Student conversations

The four proposed kinds have arities of one (Faculty inquiry), two (Counselor direct), "two plus a
source" (case coordination) and "one requester plus a source" (Referral coordination). The binding
constraints are: `student` NOT NULL `PROTECT` (`models.py:27-29`), a two-shape `CHECK`
(`models.py:80-97`), a partial unique for one-open-Office-per-Student (`models.py:110-114`), the
4-field authenticated encryption binding (`content.py:40-46`), and the Office-by-else authorization
branch (`policy.py:62-67`).

| Dimension | **Option 1 — typed columns on `GuidanceThread`** | **Option 2 — participant/link table** | **Option 3 — compat layer, incremental constraints** |
|---|---|---|---|
| Student nullability | `student` becomes nullable when the first non-Student kind is permitted; a `CHECK` forbids it for that kind, so a Student cannot be smuggled in | same, plus a `participant.role` row set; the legacy column must still be nullable | keeps `student` required and stores the "real" requester elsewhere → **either a fake Student or a second table**; this is where the disclosure hazard lives |
| Per-kind cardinality | expressible as `CHECK` (`kind ⇔ exactly these columns`) — one row, one constraint, mirrors the shipped `gm_thread_family_shape` (`models.py:80-97`) | **not** expressible as a row-local `CHECK`; needs `DEFERRABLE` triggers or service-side counting, and a race window between two inserts and their participant rows | unenforced initially; constraints land later, so a bad row can be written and read in between |
| Unique indexes | partial uniques per kind on plain columns (`(routing_college, requester)`, `(referral)`, `(pair_first, pair_second)`, `(grant, student_subject)`) | partial unique must span the parent+child tables → impossible in one index; uniqueness degenerates to service logic | same as Option 2 until the tightening migration lands |
| Locking | one table, one `select_for_update(of=("self",))` — the shipped discipline (`services.py:147-152,203-206,247-251,296-300`) extends unchanged | pair creation must lock two participant rows in a canonical order **and** the parent, or rely on advisory locks: new deadlock surface in the hottest write path | mixed; both regimes live at once during the compat window |
| Old-thread compatibility | unchanged rows keep every value; the two legacy shapes stay exactly as constrained | requires a **backfill** of participant rows for every existing thread the moment participants become the authorization source — otherwise existing chats resolve to zero readers | best-in-class for old rows by construction, worst for invariants |
| DTO/serializer compatibility | additive nullable fields; `student` can stay required until the first non-Student kind ships, so `contracts/openapi.json` need not move in GMSG-1 | response shape must grow a participants array → contract change forced in the foundation slice | unchanged until the compat layer leaks into DTOs |
| Encryption binding preservation | untouched — the AAD is `(thread_id, message_id, sequence, sender_id)` (`content.py:40-46`) and none of those columns move | untouched for the same reason, **provided** no message is ever re-parented to another thread | untouched |
| Backfill | none required for GMSG-1 (columns nullable, no new rows) | full participant backfill in the same migration | none, by design |
| Fresh install vs upgrade | one `CreateModel`-free path: fresh installs run `0001`+`0002`, upgrades the same; both must be asserted | two-table invariant means fresh-vs-upgrade divergence risk if the backfill is data-only | easy to get right, easy to leave permanently half-migrated |
| Rollback | reverse `0002` drops nullable columns; legacy constraint `gm_thread_family_shape` must be re-added **before** drop, so rollback needs a `0003_revert` rather than an unapply | rollback must restore the pre-backfill state and any thread created through participants becomes orphaned | rollback trivial, but so is the safety |
| Verdict | **recommended** | rejected | rejected |

**Recommendation (D-GMSG-19): Option 1, staged.** The domain already proves the pattern —
`gm_thread_family_shape` is a per-kind `CHECK` over exactly these columns (`models.py:80-97`), and the
proposal itself warns against a membership surface ("never accept client-supplied arbitrary
participant lists", line 8176). Options 2 and 3 both make `student` (or its backfill) an authorization
input for at least part of the migration.

### The named hazard this design exists to avoid

Proposal line 8656: *"A naive nullable-Student migration without revised queries and serializer access
rules may create immediate information disclosure."* Concretely, at this base:

1. **`policy.py:62-67`** — `require_thread` treats *any* thread that is not `COUNSELING` as
   College-scoped Office. A `FACULTY_INQUIRY` row carrying `routing_college` would be readable by every
   COUNSELOR/GSS in that College the instant it exists. Same for `authorized_threads`
   (`policy.py:48-49`).
2. **`models.py:27-29` + `policy.py:47,61`** — writing the referred Student into `student` to satisfy
   NOT NULL makes that Student a full participant: they can list, open, read, mark read, receive
   `messages.thread_changed` (`policy.py:151`) and reply to Faculty–GCO correspondence. This is the
   proposal's own critical warning (lines 8074, 8948) and it is reachable through the *natural*
   nullable-Student shortcut.
3. **`api.py:53`** — `GuidanceThreadResponse.student` is required, so a nullable column without a DTO
   rule forces either a fabricated person or a serialization crash.
4. **`work.py:35-36`** — `latest_sender_id = student_id` would silently classify new-kind threads as
   never-reply-needed (a leak by omission rather than disclosure) — and if rewritten naively to
   "anyone's unread", College-scoped staff would see Faculty threads in a workload list.

Therefore the ordering rule: **authorization matrix first (GMSG-1, while only two kinds exist),
nullability second (GMSG-2/3, in the slice that needs it), creation affordances last.**

## 2. GMSG-1 — the smallest safe foundation

**Goal:** make `GuidanceThread` structurally able to express the six kinds and make authorization
kind-explicit and deny-by-default, with **zero** user-visible change: no new kind can be created, no
DTO field changes, no new capability is granted, and no FE file is touched.

### 2.1 Files to change (later slice; none touched here)

| File | Change | Why |
|---|---|---|
| [be/compass/guidance_messages/models.py](../../be/compass/guidance_messages/models.py) | add the four `ThreadKind` values (`:11-13`) as **reserved**, widen `kind` (`:23`, `max_length=16` → 32: the longest proposed code is 26 chars), add nullable typed columns `requester`, `direct_first_user`, `direct_second_user`, `student_subject`, `institutional_endpoint`, `relationship_referral`, `relationship_case_grant` (keeping `student`, `counselor`, `routing_college`, `relationship_appointment`, `assigned_to` exactly as-is) | D-GMSG-19/20 |
| same, `Meta.constraints` | extend the existing `CHECK` (`:80-97`) into a per-kind allowlist that **re-states the two legacy shapes verbatim** and marks the four new shapes `NOT VALID`-equivalent (i.e. the CHECK admits them only when `student IS NULL`, which no insert path can produce yet); add the per-kind partial uniques (`:110-114` untouched) and `direct_first_user < direct_second_user` | per-kind cardinality without touching old rows |
| [be/compass/guidance_messages/policy.py](../../be/compass/guidance_messages/policy.py) | replace the else-branch (`:62-67`) and the two-kind filters (`:48-52`, `:151-155`) with an explicit kind→(role, capability, resource) matrix that **denies any unlisted kind**; keep `require_actor`'s role-before-capability order (`:33-40`) unchanged | D-GMSG-29, the blocking item |
| [be/compass/guidance_messages/services.py](../../be/compass/guidance_messages/services.py) | factor `_lock_thread`/canonicalization helpers used by future opens; add a kind argument to internal `_audit` metadata (already emits `kind`, `:54`); **no new public function** | reuse the shipped lock order (`:203-206`) |
| `be/compass/guidance_messages/migrations/0002_kinds_and_participants.py` (new) | additive: `AddField` ×N, `AlterField` on `kind` length, `AddConstraint` ×(new CHECK + partial uniques), **plus a `RunPython` no-op** that fails loudly if any legacy row violates the re-stated legacy CHECK | upgrade ≡ fresh install |
| [be/compass/accounts/policy.py](../../be/compass/accounts/policy.py) | **not changed in GMSG-1** — capability catalog (`:152-172`) and grants (`:635,658-660,702-704,727-728`) move only in the slice that exposes a kind | keeps the ceiling honest |
| [be/compass/guidance_messages/api.py](../../be/compass/guidance_messages/api.py), `contracts/openapi.json`, `fe/src/lib/api/generated/**`, all `fe/` files | **not changed in GMSG-1** | `student` stays required (`api.py:53`), no new kind is reachable, so the contract is byte-identical; hand-editing generated output is prohibited (`fe/AGENTS.md` §4/§57) |

### 2.2 Migration ordering and rollback

1. `0002` additive columns (nulls allowed) → no rewrite of `guidance_messages_guidancemessage`, and
   `kind` widening is a `varchar` length change (metadata-only in PostgreSQL).
2. `0002` constraint swap in the **same** migration: drop `gm_thread_family_shape`
   (`models.py:80-97`) and re-add the generalized CHECK whose legacy half is character-for-character
   the old predicate. Doing both in one transaction means no window where an unconstrained row is
   writable.
3. Add per-kind partial uniques (all inert — no rows can violate them yet).
4. Deploy the policy/services rewrite (matrix, deny-by-default) **with** the migration in one release,
   because the matrix is what makes the new columns safe.
5. Rollback: a forward `0003_revert` that restores the original CHECK name/predicate and drops the new
   columns. Never unapply `0002` in place on a shared database. Rollback is only safe if no new-kind
   row exists — guaranteed, because GMSG-1 creates none.

Preserved invariants (must be asserted, not assumed): thread/message UUIDs, `sequence`,
`(sender, client_message_id)`, `last_sequence`, all four encryption binding fields
(`content.py:40-46`), the `PROTECT` graph, `default_permissions = ()` (`models.py:71,131,156,205`) and
the concealment contract (`policy.py:55-69` → `api.py:196-201`).

### 2.3 Tests to add in GMSG-1 (targeted; no full suite)

- **Constraints:** for each of the four reserved kinds, an ORM-level insert attempt is rejected while
  no service path can create one; the two legacy shapes still insert exactly as before;
  `direct_first_user < direct_second_user` rejected; each partial unique blocks its duplicate under a
  concurrent pair (race test alongside `be/tests/test_guidance_messages_concurrency.py`).
- **Negative authorization:** IT Admin and Institutional Officer denied for **every** kind even with
  `UserCapabilityOverride` deliberately granting `guidance_messages.manage`
  (`accounts/models.py:337`, `policy.py:33-40`); Head designation grants no Counseling or peer access
  (`policy.py:51,63`); GSS denied Counseling; a Student subject never sees a subject-only thread;
  unknown/foreign UUIDs still 404 identically.
- **DTO compatibility:** `GuidanceThreadResponse` golden-shape test asserting `student` remains
  required and `contracts/openapi.json` operation count stays 21.
- **Encryption binding:** round-trip one message per kind-shaped thread, assert the AAD fields are
  unchanged (`content.py:40-46`), plus a tamper test (swap thread/sender/sequence →
  `GuidanceMessageContentUnavailable` → 503).
- **Migrations:** fresh install (`migrate` from empty) and upgrade (from `0001` with legacy rows) both
  end at the same schema; existing rows survive byte-identical (sequence, ciphertext, timestamps).
- **Protected existing tests:** all 116 functions in `be/tests/test_guidance_messages*.py` and the 4 FE
  message test files must remain green (counts verified in `current-state.md` §11).

### 2.4 Explicitly not in GMSG-1

No new user-visible kind, no new capability, no creation endpoint, no FE change, no notification event,
no typing, no Seen, no read-cursor schema change, no retention/export code, no feature flag
(any phasing is code-owned in the `provisional_activation.py:5-11` style), and no
`contracts/openapi.json` regeneration.

## 3. Sequencing for GMSG-2..GMSG-8

| Slice | Scope | Depends on | Contract/client impact |
|---|---|---|---|
| GMSG-2 | Faculty general inquiry + GCO intake view | GMSG-1; **D-GMSG-01** (routing) must be answered; `student` becomes nullable in this slice with the forbidding CHECK | new operations + `student` optional → OpenAPI + generated client + FE |
| GMSG-3 | Referral coordination | GMSG-1; `Referral.submitted_by` (`referrals/models.py:54-61`) verified shipped; **D-GMSG-09** | one open + per-thread ops; subject never in DTO for the Student |
| GMSG-4 | Counselor direct | GMSG-1; **D-GMSG-05/06**; no external domain dependency | pair operations + bounded peer directory |
| GMSG-5 | Case coordination | GMSG-1; **D-GMSG-07/08** *and* a real CONT communication scope + single predicate service (D-GMSG-29) — implemented, dormant pending D-GMSG-08; see [`docs/gmsg-5/README.md`](../gmsg-5/README.md) | grant-bound thread ops |
| GMSG-6 | Read receipts | GMSG-1; **D-GMSG-03/04/14**; monotonicity hardening (D-GMSG-26) | response fields for Seen |
| GMSG-7 | Typing | GMSG-1; **D-GMSG-13**; new `messages.typing_changed` registry entry + HTTP signal (D-GMSG-24) | realtime protocol both sides |
| GMSG-8 | Unified workspace, purpose filters, work/notification alignment, full gates | all above; **D-GMSG-12/15/16**; fixes D-GMSG-25 surfacing | FE-heavy; full regression + browser + UAT |

GMSG-5 waits for a real authority rather than shipping dormant code: `ContinuitySourceKind` has no
communication member (`continuity_models.py:34-41`) and the docstring disclaims content authority
(`:1`), so any GMSG-5 code today would have to invent the very authorization the CONT slice refused to
grant — and proposal line 8896 forbids deploying case messaging before the contract is real.

## 4. Future test plan (proposed, none executed in GMSG-0)

- **Regression floor:** the 116 backend functions in `be/tests/test_guidance_messages*.py` and the 4 FE
  files (`fe/tests/guidance-messages.test.mjs` 36 tests;
  `guidance-messages.browser.mjs` 35 checks; `guidance-messages-contextual.browser.mjs` 20;
  `guidance-messages-staff-operations.browser.mjs` 26) stay green from GMSG-1 onward.
- **New kinds (GMSG-2..5):** positive and negative authorization for each of the six roles × six kinds
  in `access-matrix.md` §2; referred-Student denial; IT Admin/Institutional Officer denial **with a
  deliberately granted capability** (the D-GMSG-29 guarantee); handler/scope revocation mid-thread;
  grant expiry and revocation during an active thread; realtime recipient recomputation after each of
  those (asserted through `policy.recipient_ids:149-165`, not by inspecting the payload).
- **Read receipts (GMSG-6):** monotonicity under concurrent mark-read and a racing send; no Seen from a
  background fetch or list refresh (drive the FE path in `guidance-conversation-data.ts:129-152`);
  no fabricated historical Seen on legacy threads; handler change does not regress Office Seen.
- **Typing (GMSG-7):** payload carries no body/draft; TTL expiry locally after a dropped stop; throttle
  bounds heartbeats; forged thread UUID / forged sender rejected
  (`protocol.py:213-231`, `app.py:334-348`); revoked authorization stops delivery.
- **Migration:** fresh install vs upgrade from `0001` with real legacy rows; rollback `0003_revert`;
  historical ciphertext still decrypts after every migration (`rotate_guidance_message_encryption.py
  --dry-run` is the natural verifier — **not run in GMSG-0**).
- **Full suites, Django checks, OpenAPI check, typecheck/lint/build, browser suites, UAT:** only at
  GMSG-8, per the project rule that the family's final slice carries the broad gates.

No test is claimed to pass in this document, because none was run.
