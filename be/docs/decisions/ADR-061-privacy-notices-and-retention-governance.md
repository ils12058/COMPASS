# ADR-061: Privacy Notices, Acknowledgments, and Retention Governance

- Status: Accepted
- Date: 2026-09-26
- Scope: Privacy Governance expansion after ADR-045

## Context

The DPO workspace needs authoritative notice, retention, and global review discovery surfaces. ADR-045 established the access boundary and initial Processing Activity, Review, Incident, and curated Activity records. That foundation deliberately left broader governance workflows and retention execution for later decisions. A frontend cannot reconstruct an accurate review queue by crawling paginated Processing Activity reviews.

## Decision

The DPO remains an `INSTITUTIONAL_OFFICER` with the `DPO` designation. Existing designation-derived `privacy_governance.view` and `privacy_governance.manage` capabilities apply. All DPO management mutations require recent MFA. This expansion grants no access to underlying confidential Student-domain records and adds no capability codes.

A Processing Activity gains a descriptive `data_subject_choice_summary` and an optional protected link to an internal Retention Policy. Its existing external/historical `retention_policy_reference` and `policy_basis_reference` remain. The choice summary is human-entered governance prose; COMPASS does not interpret it as executable policy or legal basis. Retention Policies record scope, trigger, period, disposition, policy reference, and review dates as bounded plain language. They do not run deletion, archival, anonymization, or notifications. A policy assigned to an active Processing Activity cannot be retired until the DPO reassigns or clears it. Existing rows retain a null internal policy link. No policy or notice text is seeded.

Privacy Notices have stable families and numbered revisions. A family can have one draft and one published revision; publishing atomically supersedes the prior published revision and records the DPO audit event. Published and superseded content is immutable through the API. Revisions use only `PUBLIC`, `STUDENT`, and `STAFF` audiences, bounded plain text, and an effective date that cannot be in the future at publication. Public clients see current published `PUBLIC` revisions. Active authenticated Students see `PUBLIC` and `STUDENT`; other active accounts see `PUBLIC` and `STAFF`.

An acknowledgment records only that the authenticated account acknowledged the exact current published revision at a timestamp. It is self-only, idempotent, and does not carry forward to a later revision. Acknowledgment is **not consent**, waiver, or a legal-basis conclusion. Purpose-specific actual consent remains owned by its domain, including E-Counseling recording, transcription, and transcript storage. There is no generic privacy consent checkbox, global application acknowledgment gate, or per-person DPO acknowledgment dashboard.

A global filtered Reviews/PIAs endpoint provides the operational queue with a small Processing Activity identity, while the nested endpoint remains. Overview `open_review_count` keeps its existing status semantics. DPO mutations use synchronous AuditEvents with minimized metadata and curated Privacy & Security Activity presentations; ordinary user acknowledgment does not enter that curated feed.

## Consequences

The future `/portal/privacy` workspace can show Processing Activities, Reviews/PIAs, Privacy Notices, Retention Policies, Incidents, and Privacy & Security Activity using authoritative API pages. A general user can read applicable current notices and acknowledge a required revision. The frontend must label acknowledgment accurately and safely render notice body as plain text. No legal content, compliance score, legal determination, automatic retention execution, or confidential record browser is introduced.
