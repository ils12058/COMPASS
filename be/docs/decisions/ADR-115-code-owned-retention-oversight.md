# ADR-115: Code-owned retention policy register and read-only oversight

- Status: Proposed (PG-1A PR 2). Becomes Accepted on owner approval.
- Date: 2026-10-16
- Follows: [ADR-114](ADR-114-decommission-in-app-disposition.md), which stopped in-app disposition
- Supersedes for future operation: the retention routes, capabilities and workspace of
  [ADR-072](ADR-072-operational-retention-and-disposition.md) and the "Versioned retention and
  verified disposition" section of [ADR-092](ADR-092-ecounseling-media-governance-v2.md)
- Preserves: ADR-011 Audit Trail; ADR-045/ADR-061 Privacy Notices and the DPO boundary; ADR-069's
  rule that Privacy Governance shows only what COMPASS really does; ADR-092 consent, custody and
  provider cleanup; ADR-114 tombstones and fail-closed services

## Context

ADR-114 stopped every destructive path but left the rule, hold, approval and case routes, the
`privacy_governance.retention.manage` and `.approve` capabilities, and the operational workspace in
place. COMPASS must not present itself as a records-disposition approval or destruction platform.
No institutionally adopted retention period has been verified for any COMPASS record category.

## Decision

1. **Code-owned register.** `compass/privacy_governance/retention_policy_register.py` holds frozen
   `RetentionPolicy` entries: `category_code`, `category_label`, `adoption_status`,
   `retention_period`, `policy_reference` and `effective_date`. There is no model, table, setting,
   environment variable, capability or API that can change it. Changing an entry requires an
   authorized institutional policy source and a reviewed code change. Code ownership is
   implementation ownership; developers do not decide University retention periods.
2. **No invented policy.** The three entries (Graduate Tracer responses, E-Counseling recordings,
   E-Counseling transcripts) are `NOT_ADOPTED`, with no period, reference or date. `NOT_ADOPTED`
   means no adopted policy has been verified and recorded in COMPASS. It does not mean the
   University has no applicable schedule. Legacy rules, contract versions, triggers, durations and
   actions are not carried over; an ACTIVE legacy rule is not adoption.
3. **Validation.** Entries reject untyped or coerced values. A `NOT_ADOPTED` entry rejects any
   period, reference or date, including empty strings. `ADOPTED` requires nonblank period wording,
   a policy reference and an explicit date. Code can require those terms; it cannot verify that an
   approval is genuine, so the reviewed change must cite its institutional source. Categories are
   unique, and an invalid register fails at import.
4. **Not enforcement.** The register queries no records and computes no eligibility. It creates no
   case, schedules no task, and never anonymizes or deletes. `ADOPTED` changes only what oversight
   displays.
5. **Read-only API.** `GET /api/v1/privacy/retention/policies`
   (`privacyGovernanceListRetentionPolicies`) requires authentication and the effective
   `privacy_governance.retention.view`. It returns only the six fields, in register order, and never
   reads the legacy ledger. No other method exists on the route.
6. **Legacy routes removed.** All 14 ADR-072 retention operations are removed from the router and
   the contract: categories, summary, rule list, detail, create, update, activate and retire, plus
   case list, detail, hold, release-hold, approve and retry. Their paths return 404. ADR-114's
   fail-closed services stay as a fallback until PG-1A PR 3.
7. **Capabilities.**
   - `privacy_governance.retention.view` is kept and redefined as "View retention policy oversight".
     It grants no rule, hold, approval or disposition authority. The DPO designation keeps it.
   - `.retention.manage` and `.retention.approve` leave the definitions, the DPO grants and the
     dependencies. They are added to `RETIRED_CAPABILITY_CODES`, so `sync_identity_policy` deletes
     their persisted role grants, designation grants, user overrides and capability rows.
   - Historical AuditEvents are not changed.
8. **Frontend.** One read-only Retention Policies page replaces the Retention & Disposition
   workspace. It has no create, edit, activate, hold, approve or retry action, and no Disposition
   History page. Former rule and case URLs redirect to it. Student-facing copy no longer says that
   retention rules and holds govern captured media.
9. **History kept, not served.** The rule, case and hold tables, AuditEvents, anonymous Graduate
   Tracer contributions and disposed-participation markers, and disposed E-Counseling markers are
   unchanged. `DispositionCase.source_id` stays internal for the E-Counseling resurrection fences and
   restore reconciliation. Historical events remain visible in Privacy & Security Activity, with
   past-tense descriptions.

## Unresolved

The adopted periods for these categories are still undecided. So are the National Archives schedule
coverage, the external disposal procedure, disposal of legacy V1 provider-held media, and backup
retention. These are listed in ADR-114. Each still needs an institutional decision.

## Consequences

- Deployment must run `sync_identity_policy`. The staging deploy already does, after `migrate` and
  before `up -d`. Until it runs, old persisted grants for the retired codes remain in the database;
  they are inert, because the codes are absent from `CAPABILITY_CODES`.
- Backend first, then frontend. The old frontend on a new backend gets 404 on the retired routes,
  so no mutation is possible. The new frontend on an old backend cannot load the register.
- A rollback to a pre-ADR-115 build re-creates the retired grants through sync, but not the purged
  overrides. ADR-114's refusal still blocks every mutation.
- PG-1A PR 3 removes the tombstones after a verified drained broker, deletes the fallback services,
  and may add database write protection to the legacy tables.
