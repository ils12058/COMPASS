# FAC-2 implementation preflight

Verified on 2026-10-31 after fetching origin: integration and the clean local
checkout both at `1778359f` (merged FAC-1 PR #348). Branch:
`codex/fac-2-faculty-referrals`; target: `integration/ux15-modernization`.

Read FAC-1's preflight, FAC-2 contract and validation record, ADR-113, the current
Referral services/models/API/encryption/template, account policy and managed
affiliation, authentication/session and rate-limit services, Organization catalog
gate/StudentAffiliation writers, Audit, Notifications, and the published development
booklet's Proposal #7. The booklet is historical proposed direction; current owning
source is authoritative for implementation facts. No digital form or lookup approval
has been supplied. No staging/main change, deployment or merge is authorized here.

## Current findings

- Faculty exists with FAC-1's empty capability ceiling and controlled home College.
  There is no Faculty submission, Student confirmation or own-submission API.
- GCO `create_referral` validates its own operational actor and Student College scope,
  locks current identities, uses actor-bound creation digests/fingerprints, allocates
  `REF-YYYY-NNNNNN` in Philippine time and writes encrypted content plus Audit atomically.
  The allocator is shared domain machinery, not a Faculty-specific numbering system.
- `Referral` has no authenticated Faculty origin. `recorded_by` remains the GCO
  encoder; a historical name is not an ownership relationship. `received_at` is not
  automatically set by current creation and must not become a submission timestamp.
- ADR-113 and the actual `ucn_referral_slip.html` require Student name, Course/Yr &
  Blk, reason, referrer printed-name/signature area and date. Receipt date/time,
  reference, GCO actions/remarks/status occupy the Guidance/Coordinator portion.
  A server-derived printed name is not a digital signature. The approved paper
  identity does not itself approve digital capture or a signature substitute.
- Referral reason/referrer/status/void reason use a bound encrypted envelope; the
  existing GCO DTO and source PDF disclose content inappropriate for Faculty.
- StudentAffiliation writers take the catalog gate and Student row lock. Faculty
  home writers take the gate and current account lock. Reuse these orders; do not
  introduce a Student placement writer or a Faculty-home routing fallback.
- CONT supplies an established explicit approved-policy-provider pattern, defaulting
  to None. FAC-2 will use a separate Faculty domain boundary with validated evidence
  and a matching append-only Audit activation record, not flags or capability alone.

## Ownership and planned dependency changes

| Files | Responsibility |
| --- | --- |
| `accounts/{policy,services}.py`, `account_management/services.py` | Two Faculty-only capabilities, dependency-coherent bounded ceiling and override eligibility; all existing roles' grants preserved |
| `referrals/models.py`, additive migration | Explicit legacy/GCO/Faculty channel; immutable authenticated submitter/time/home/Student-College and approved-policy provenance; no historical identity inference |
| `referrals/services.py` | Extract canonical encrypted creation/Audit persistence below unchanged GCO authorization; shared annual allocator |
| `referrals/faculty_policy.py` | Separate evidence-gated lookup/submission/read policies; default denial and auditable activation contract |
| `referrals/faculty_placement.py` | Read-only Student placement resolver with SAR-compatible boundary |
| `referrals/faculty_services.py`, `faculty_api.py` | Current actor/session locks, bounded exact confirmation, signed expiring actor-bound confirmation, transactional submission/replay, allowlisted own projections |
| `audit/actions.py`, `api/v1/router.py`, `contracts/openapi.json` | Audit actions, separate routes under the existing Referrals tag, canonical generated contract |
| `be/tests/`, `.github/scripts/backend_ci.py` | Positive/negative authorization, real PostgreSQL races, additive migration preservation and CI registration |
| `docs/fac-2/` | Decisions, privacy/form mapping, policy register, FAC-3/FAC-4 handoff and observed validation |

Frontend scope is regeneration/compatibility validation only. FAC-1's holding page
continues to state that digital Referrals are unavailable. No UI, notifications,
GCO acknowledgment/closure, teaching-roster inference or academic migration is added.

## Inherited CI evidence

FAC-1's first hosted backend run failed missing bundle registration; its merged
follow-up fixed that. Backend rerun `41204815181` completed with failures in five
test shards. Its prepare phase proceeded, but this does not establish a full
backend pass. FAC-1's broad frontend run also has documented legacy UX layout
assertion failures. FAC-2 will report inherited failures separately and use focused
and consolidated domain checks; it will not rewrite unrelated UX15/SIMPLIFY work.
