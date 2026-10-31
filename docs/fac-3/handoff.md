# FAC-4 acknowledgment, closure and Notifications handoff

FAC-3 delivers the Faculty frontend. FAC-2 still owns intake authorization,
immutable provenance, encryption, Student placement, counters and idempotency.
No institutional digital-form/disclosure provider is installed or activated here.
FAC-D1–D10 remain governed by the FAC-2 decision register.

## Extend only actual domain facts

The current own DTO and wire enum contain only **Submitted**. FAC-4 must establish
real authorized GCO acknowledgment/administrative-closure transitions, actors,
timestamps, audit and concurrency before adding states to OpenAPI and the UI.
Opening a record, delivering a Notification or completing Counseling/Follow-Up is
not acknowledgment or administrative closure. Neither state may imply clinical
resolution, treatment or confidential activity.

Keep immutable submitter/home/Student-College and policy provenance, and preserve
`recorded_by` versus acknowledgment actor semantics. Reconcile existing receipt
facts rather than creating a competing writer. Resolve exceptional void visibility
before expanding tracking; FAC-2 currently omits voided own records and returns
404 for them. Do not reinterpret that absence as Closed, Rejected or Received.

## Faculty-safe navigation and disclosure

The destination for a permitted Faculty referral event is
`/portal/faculty/referrals/{referral_id}`. The GCO path
`/portal/referrals/{referral_id}` remains inaccessible to Faculty. Future approved
Notification producers must define a canonical target type/recipient/disclosure
contract before adding frontend mappings. No such producer or target mapping is
invented by FAC-3; the existing Notifications Center and Profile are reused.

Do not notify the named Student automatically. Settle event-specific Faculty/GCO
recipients, content, trusted-origin email/deep links and retention under the existing
NOTIF boundary. Never copy the submitted reason, confirmation value, internal notes,
Actions, Follow-Ups or clinical outcome into notifications or ordinary Faculty DTOs.

## Preserve interaction guarantees

- Availability facts are advisory and independent. Own-list success never enables
  new submission. Keep the current backend authority checks on every operation.
- Mutations require a deliberate action. Session/step-up recovery, expiry, policy
  refresh, restored connectivity and background reads never resubmit a form.
- An uncertain submission retains the exact key/body for canonical replay, not a
  regenerated confirmation or a new key. A changed intended submission requires
  explicit editing/review. No durable confidential draft storage is available.
- Continue minimal own-list/detail fields and account-owned cache boundaries.
  Extend the generated contract first; no generic GCO DTO reuse or fabricated
  timeline, acknowledgment count, PDF or counselor identity.
- Review any realtime/Notification-driven freshness deliberately. Hints may request
  canonical refetches; they must not carry a reason or become authoritative status.

## Deployment limits

No deployment, staging/main modification or live approval occurs in FAC-3. A future
authorized rollout needs matching backend/frontend contract versions, existing FAC-2
schema and identity synchronization, actual institutional decisions/evidence custody,
and a reviewed provider adapter. The availability route does not install that adapter.
Positive synthetic screenshots and passing tests do not constitute approval or UAT.
