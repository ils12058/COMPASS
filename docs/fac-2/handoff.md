# FAC-3 frontend and FAC-4 operational handoff

## FAC-3 consumers

Use the generated Referrals API functions/types/query keys from
`contracts/openapi.json` after Orval generation. Operation IDs and route shapes
are in the README. Do not duplicate DTOs or transport, accept privileged fields,
or use the Account directory/GCO Student selector for Faculty confirmation.

The two Faculty capabilities indicate functional eligibility, not institutional
activation. The current backend returns explicit 403 policy-denial codes:
`faculty_referral_lookup_policy_unconfirmed`,
`faculty_referral_submission_policy_unconfirmed`, or the more general
`faculty_referral_policy_unconfirmed` for invalid/missing approval evidence.
Handle them as unavailable without implying approval or exposing a working form.
Successful own-list access alone is not proof that Student confirmation and new
submission have been approved. If a dedicated availability projection is needed,
review its backend contract in FAC-3; do not invent a frontend feature flag.

An approved workflow should:

1. Confirm one exact identifier by POST with CSRF. A negative response says only
   that the Student cannot be confirmed; never distinguish absent, disabled,
   unplaced or out-of-policy identity. Render only the returned display name.
2. Keep the signed `confirmation` and its deadline in form memory. Any server
   `faculty_referral_student_unavailable` 409 means re-confirm under current state;
   do not silently choose a College, Student or fallback counselor.
3. Capture the actual source form's Course/Yr & Blk and confidential reason.
   Course text is declared, not a verified academic placement. Do not add a teaching
   verification badge, contact-basis attestation, signature mechanism or new form
   fields without the recorded institutional decisions and contract version.
4. Generate one idempotency key per intended submission, retain the exact body/key
   for an uncertain result and require deliberate retry. Editing a body requires a
   new intended submission/key. 201 is creation; 200 is canonical replay. A 409
   key conflict is not a duplicate success. Never auto-submit after re-confirming,
   refreshing a session, policy change or recovering an error.
5. Clear sensitive drafts only after canonical success or deliberate discard. An
   expired ticket can still resolve an already committed identical replay while
   current ownership/session/policy remain valid; it cannot create a new Referral.
6. Read only the Faculty own projections for lists and details. They contain no
   reason readback, GCO receipt/actions/remarks, Follow-Up, clinical outcome or PDF.
   Keep canonical pagination and handle empty/loading/error/background refresh.
   404 is intentionally indistinguishable for absent, foreign, GCO-only or voided
   records; do not probe alternative GCO routes to recover one.
7. Say **Submitted** only after a committed server response. Do not show Received
   by GCO or Administratively Closed from transport delivery, a page view or any
   private domain's status. No Student Referral Notification is authorized.

401 revalidates the real session via existing session handling; 403 preserves
backend denial. 429 honors Retry-After and never exposes account-existence detail.
503 on confirmation preserves input but cannot reuse an unconfirmed result as a
new authoritative identity. No unsafe request is replayed automatically.

FAC-2 intentionally leaves the existing holding Home/navigation intact. FAC-3 owns
the eventual accessible, responsive submission/tracking UI and its browser/UAT work.

## FAC-4 GCO integration

The canonical `Referral` now identifies origin independently of `recorded_by`:
Faculty channel plus immutable `submitted_by`, `submitted_at`, saved home/Student
College UUIDs and the approved policy Audit record. GCO encoding still uses
`recorded_by`; historical unspecified records remain unspecified. Never infer
Faculty ownership from encrypted form referrer text or overwrite saved provenance.

GCO source list/detail/PDF, Student College scope, status notes, Actions, Call Slips
and void safeguards retain their existing contracts. Faculty-origin records enter
that same domain only after an actually permitted submission. FAC-4 can add an
authorized GCO origin/acknowledgment projection deliberately; do not expose an
internal DTO through the Faculty router.

Before adding receipt or closure, settle FAC-D5/D6: define exact GCO actor/scope,
state/version checks, audit event, timestamp semantics and concurrency. Reconcile
existing historical `received_at` facts without backfill or a second competing
received-state writer. Acknowledgment must be an actual authorized transition,
not Notification delivery or opening a record. Closure must describe administrative
handling, not clinical resolution or completion of a linked private task.

Faculty own DTO states must extend only with real approved transition evidence.
Settle void/exception visibility before claiming active tracking of a voided record;
FAC-2 currently omits it. Existing GCO void does not erase authenticated origin.
Notifications require separate event-specific recipient/disclosure approval under
the existing NOTIF policy, trusted origins and authenticated deep-link boundaries.
Submission currently emits no Notification, Appointment, Action or Follow-Up.

## Deployment compatibility for later authorized work

No deployment is performed by FAC-2. A future approved rollout must migrate the
additive Referral schema, synchronize the two canonical capabilities, regenerate
the matching client and verify all compatible web/worker/CLI writers. The source
form/encryption key configuration remains the existing one. Keep approval providers
absent until actual institutional decisions, evidence custody and activation
adapter review are complete. Do not activate by environment settings, raw grants
or a manually inserted Audit row. Once Faculty records exist, preserve the schema
and provenance; rollback is compatible code/roll-forward, not dropping history.
