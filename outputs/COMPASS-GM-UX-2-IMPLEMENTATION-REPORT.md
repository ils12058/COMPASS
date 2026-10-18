# COMPASS-GM-UX-2 — Implementation Report

**Repository:** `ils12058/COMPASS`

**Base:** `origin/staging` at `57ff8ecf` (`feat: add program-based academic classification`)

**Branch:** `codex/compass-gm-ux-2`

**Pull request target:** `staging`

## Summary

F4 now uses the current submitted Individual Inventory as its source of academic context. New F4
requests require an exact canonical Bachelor's Program and a supported 1st–4th Year Level; COMPASS
derives the saved Year Level from Inventory. Self-service and GCO-assisted forms display that value
read-only. A changed pre-issuance Year Level correction must agree with the request's linked
submitted Inventory.

F6 now treats the reported degree as a credential-specific claim rather than deriving it from the
Student's current or highest academic classification. Active Students with any recorded lifecycle
status (`CURRENT`, `GRADUATED`, or `FORMER`) may submit F6, so later UCN postgraduate enrollment does
not erase a UCN alumnus's historical request access. F6 remains scoped to a previously completed
UCN Bachelor's degree. Current Inventory, Program, affiliation, postgraduate status, catalog
suggestions, and free-text degree names do not establish that qualification.

There is no authoritative completed-degree source or recorded GCO verification outcome in COMPASS.
F6 degree and date remain explicitly self-reported; a request stays `REQUESTED` and unverified.
This implementation adds no academic-history subsystem, degree-proof upload, migration, automatic
eligibility guarantee, deployment, or merge.

## Evidence and verification limitation

The audit found no Registrar/SIS completion feed, verified undergraduate credential record, or
documented GCO qualification-verification procedure in the active workflow. Graduate Tracer's
`graduated_college`, `graduated_program`, and `graduation_year` fields are expressly self-reported,
not Registrar-verified credentials (`be/compass/reports/graduate_tracer.py`). The Program catalog
and free-text historical fallback are request-form suggestions only.

The precise limitation is that COMPASS can accept and preserve an F6 claim, but it cannot establish
whether the Student completed a UCN Bachelor's degree, distinguish it from an external Bachelor's
degree, or record whether GCO later verified it. Lifecycle and postgraduate enrollment cannot
resolve those facts. The F6 detail and issuance-review screens now state this limitation; COMPASS
does not currently enforce or audit the manual check.

Proposed minimal GCO procedure, pending institutional approval:

1. GCO checks the claimed UCN Bachelor's degree and completion date against an approved official
   Registrar source before issuance. Postgraduate enrollment is not accepted as proof of the prior
   Bachelor's degree.
2. Record only the verification reviewer, date, approved source/reference, and outcome on the F6
   request. Avoid collecting a document copy until the institution approves that privacy practice.
3. Issue only after a positive result; return unresolved claims for verification and do not issue a
   claim confirmed as an external Bachelor's degree.
4. GCO approves the evidence source and procedure before COMPASS adds a verification field or
   issuance gate. No such gate is claimed by this change.

The architecture amendment is recorded in
[ADR-033](../be/docs/decisions/ADR-033-good-moral-request-and-issuance-foundation.md), and the
integration handoff now reflects the implemented behavior and remaining GCO decision.

## Synthetic credential-specific scenarios

| Scenario | F4 behavior | F6 behavior | What COMPASS knows |
| --- | --- | --- | --- |
| UCN Bachelor's alumnus re-enrolled in local MIT postgraduate Program | Blocked because the current Inventory Program is Master's | Request remains available | Inventory indicates current postgraduate context; it does not prove or disprove prior UCN Bachelor's completion |
| UCN Bachelor's alumnus pursuing postgraduate study elsewhere, recorded UCN lifecycle `FORMER` | No current F4 context | Historical F6 self-service remains available | External postgraduate enrollment is not represented; the UCN degree remains a Student-reported claim |
| Student in a UCN postgraduate Program reports a Bachelor's degree earned elsewhere | Blocked for F4 because the submitted Program is postgraduate | Intake records only an unverified claim; no UCN undergraduate qualification is established | UCN postgraduate enrollment is not evidence that the Bachelor's degree was awarded by UCN |

Regression tests verify that the local postgraduate case receives `POSTGRADUATE_PROGRAM`, F4
creation fails with the controlled eligibility conflict, and F6 creation stays `REQUESTED` with no
Inventory link or issuance timestamps. The external-postgraduate case verifies historical F6
access from a `FORMER` lifecycle without using an academic-history record. The external Bachelor's
case remains a request claim and does not become a verified qualification.

Existing owner-only Good Moral history and exact idempotent replay remain available across lifecycle
changes. Previously saved 5th–10th Year F4 snapshots are preserved for historical reads and exact
replay; untouched legacy corrections remain allowed. Only new F4 creation and an explicitly changed
Year Level correction use the configured Bachelor's 1st–4th rule.

## Screenshots

All browser data is synthetic and all API requests were intercepted by the local harness.

- Student self-service, current Student in local postgraduate Program requesting F6:
  [screenshot](gm-ux-2/screenshots/good-moral-student/student-current-local-postgraduate-f6-request.png)
- Former Student pursuing postgraduate study elsewhere:
  [screenshot](gm-ux-2/screenshots/good-moral-student/student-former-external-postgraduate-f6-request.png)
- Counselor-assisted F4 confirmation:
  [screenshot](gm-ux-2/screenshots/good-moral-assisted-chromium/counselor-assisted-f4-confirmation.png)
- GSS-assisted F4 confirmation:
  [screenshot](gm-ux-2/screenshots/good-moral-assisted-chromium/guidance_services_staff-assisted-f4-confirmation.png)
- GSS local-postgraduate case with F4 unavailable and F6 claim available:
  [screenshot](gm-ux-2/screenshots/good-moral-assisted-chromium/gss-local-postgraduate-f6-claim.png)

## Validation

- Focused backend Good Moral suite: **156 passed**. Pytest emitted one teardown warning because
  `test_target_change_committed_while_waiting_for_student_fence` left another connection using the
  test database at teardown; all tests passed.
- Focused frontend Good Moral unit tests: **21 passed**.
- Synthetic browser checks: **13/13 assisted checks** and **2/2 Student self-service checks**.
- `pnpm typecheck`, targeted ESLint, Ruff checks, Ruff formatting, OpenAPI contract check, and
  `git diff --check` passed. `pnpm api:generate` completed.
- CI was not run. This branch has not been merged or deployed.
