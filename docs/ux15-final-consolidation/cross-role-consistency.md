# Cross-Role Consistency Audit

## Status key

- **Consistent and appropriate** — the shared contract is preserved and verified.
- **Intentionally different** — the role has a distinct presentation because its authority or work
  differs.
- **Confirmed defect** — reproduced product behavior that requires correction.
- **Unverified/manual** — automated evidence does not establish this item.
- **Deferred improvement** — outside this consolidation's scope and not a demonstrated blocker.

No production defect was confirmed in the integrated role compositions. Different Home layouts are
intentional when they follow different canonical sources and scopes.

## Comparison matrix

| Area | Student | Counselor | Head Guidance Counselor | Guidance Services Staff | Other roles |
| --- | --- | --- | --- | --- | --- |
| Greeting and context | **Intentionally different** — Student greeting, Overview context, institutional date. | **Intentionally different** — Counselor greeting and Manila date. | **Intentionally different** — same Counselor identity/date; Head designation is not an access grant. | **Intentionally different** — Guidance Services Home and authorized Office-work context. | **Consistent and appropriate** — existing general Overview title/context retained. |
| Primary actions | **Consistent and appropriate** — canonical Student Actions and existing eligible booking action. | **Intentionally different** — agenda and existing professional continuation links; no new Home mutation. | **Intentionally different** — Counselor actions plus only capability-authorized oversight destinations. | **Intentionally different** — My Work, scoped schedule, and existing workspace links. | **Consistent and appropriate** — existing Overview actions unchanged. |
| Canonical work | **Consistent and appropriate** — Student Actions remain source-owned and authoritative. | **Consistent and appropriate** — existing Work Queue order, page boundary, and owning routes. | **Consistent and appropriate** — same self-scoped Work Queue as an ordinary Counselor. | **Consistent and appropriate** — same Work Queue with existing GSS filters and route ownership. | **Consistent and appropriate** — existing Overview/work projections unchanged. |
| Summaries | **Intentionally different** — only Student-relevant backend counts; unexpected professional sections are suppressed. | **Consistent and appropriate** — existing summary meanings and null/zero semantics. | **Intentionally different** — no fabricated staff-wide metric or clinical aggregate. | **Intentionally different** — scoped Guidance Operations; duplicate Overview counts are not fetched. | **Consistent and appropriate** — existing summary composition retained. |
| Navigation | **Consistent and appropriate** — destinations derive from existing Student access/lifecycle helpers. | **Consistent and appropriate** — continuation links are intersected with current workspace visibility. | **Consistent and appropriate** — designation alone does not reveal any destination; existing capabilities still gate them. | **Consistent and appropriate** — links come from current workspace/access projections; Home does not grant actions. | **Consistent and appropriate** — existing role-visible workspaces and route checks unchanged. |
| Announcements | **Consistent and appropriate** — existing audience, pinning, and route behavior. | **Consistent and appropriate** — shared authorized announcements remain available. | **Consistent and appropriate** — same announcements as Counselor. | **Consistent and appropriate** — same shared announcements below operational areas. | **Consistent and appropriate** — existing Overview announcements retained. |
| Loading, empty, and error states | **Consistent and appropriate** — loading, failure, stale, and confirmed empty Student Actions remain distinct. | **Consistent and appropriate** — agenda and work states remain independent and actionable. | **Consistent and appropriate** — denied or absent authority is not reported as empty work. | **Consistent and appropriate** — work, appointments, and operations independently distinguish loading, empty, error, and stale data. | **Consistent and appropriate** — no role-specific Home change to existing Overview state handling. |
| Freshness and retry | **Consistent and appropriate** — source-owned freshness and Retry are retained. | **Consistent and appropriate** — existing focus/reconnect refresh and Retry; last confirmed data is labeled stale. | **Consistent and appropriate** — authorization changes conceal protected cached content. | **Consistent and appropriate** — transient failures retain labeled prior facts; authorization failure does not. | **Consistent and appropriate** — existing behavior retained. |
| Responsive layout | **Consistent and appropriate** — synthetic Home checks at 320, 360, 390, 768, 1024, and 1440 CSS px; enlarged root text. | **Consistent and appropriate** — same responsive matrix and expanded/collapsed dock coverage. | **Consistent and appropriate** — authorized and restricted Head variants included. | **Consistent and appropriate** — six widths plus 320px/200% root text; no fixture-measured overflow. | **Consistent and appropriate** — IT Admin and Institutional Officer Overview non-regression cases pass. |
| Keyboard and focus | **Consistent and appropriate** — navigation, visible focus, and form destinations tested. | **Consistent and appropriate** — agenda precedes work in reading/focus order; target links retain visible focus. | **Consistent and appropriate** — capability-gated links remain keyboard-accessible. | **Consistent and appropriate** — work links and shell actions retain keyboard access and visible focus. | **Unverified/manual** — role-specific UAT, including DPO-designated Institutional Officer, is still required. |
| Privacy and access | **Consistent and appropriate** — no professional content in Student summaries or Home previews; lifecycle/self-access gates retained. | **Consistent and appropriate** — self-Appointment source and bounded work previews exclude confidential narratives. | **Consistent and appropriate** — no Head override or cross-Counselor clinical view is added. | **Consistent and appropriate** — no Counselor Evaluation or confidential purpose content; issuance and preparation remain separate. | **Consistent and appropriate** — no UX15 expansion of IT Admin or Institutional Officer data access. |

## Intentional differences

- Student Actions are a Student-owned canonical projection; professional My Work is the canonical
  Work Queue. Combining them would invent a second task aggregator.
- Counselors see their own self-Appointment agenda. GSS sees managed Appointments only when the
  existing `appointments.manage` capability permits it and the server returns the scoped list.
- Head designation reveals only already-authorized oversight destinations. Each domain still owns
  its scope and capability checks.
- GSS operational counts come from the existing scoped Guidance Operations read model. The Home
  omits unrelated or duplicate Overview counts.
- Student, Counselor, and GSS Homes have different order and emphasis because their canonical work
  and actions differ. All retain existing announcements, clear state handling, and shared shell
  interactions.

## Evidence and limits

The three Home browser suites passed in both engines: Student **39/39**, Counselor/Head **13/13**,
and GSS **16/16**. `portal-shell-accessibility.browser.mjs` passed **6/6** in each engine.
`work-queue.browser.mjs` and `guidance-operations.browser.mjs` passed **19/19** and **20/20** in
each engine. Relevant Node tests are included in the 862/862 single-worker result.

Account changes, capability absence, stale refresh, 401/403 concealment, appointment scope,
confidential preview exclusion, and other-role behavior use synthetic browser responses. These
tests verify client presentation and request gating; they do not prove deployed backend
authorization. See [privacy and correctness](privacy-and-correctness.md) and the executable
[UAT matrix](uat-matrix.md).
