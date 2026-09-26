# ADR-045: Privacy Governance Foundation

- Status: Accepted
- Date: 2026-09-19
- Scope: DPO privacy-governance authority, governance registers, curated privacy/security oversight, and sensitive artifact release auditing

## Context

COMPASS already distinguishes primary Roles from institutional Designations. The Data Protection
Officer is modeled as the `DPO` Designation compatible with the neutral
`INSTITUTIONAL_OFFICER` Role.

That distinction is important. A DPO needs privacy-governance oversight but is not an IT
Administrator, Counselor, Head Guidance Counselor, Guidance Services Staff member, or unrestricted
reader of confidential student records.

The existing append-only `audit.AuditEvent` is authoritative for audit history. Existing
self-activity and Platform Operations activity APIs already demonstrate closed, code-owned
projections rather than exposing raw audit rows.

## DPO authority comes from the Designation

Add canonical capabilities:

- `privacy_governance.view`
- `privacy_governance.manage`

Neither capability is granted through any primary Role baseline.

Both are granted through `DESIGNATION_CAPABILITY_GRANTS["DPO"]`.

Therefore:

- plain `INSTITUTIONAL_OFFICER` has no privacy-governance authority;
- `INSTITUTIONAL_OFFICER + DPO` receives privacy view/manage;
- IT_ADMIN does not receive DPO authority merely because it manages the platform;
- Counselor and Head Guidance roles/designations do not receive DPO authority.

Privacy APIs authorize through the existing effective-capability resolver. They do not check Role or
Designation names at the route boundary.

Existing explicit capability overrides remain governed by Account Management and are not redesigned
here.

All privacy-governance mutations require `privacy_governance.manage` plus the existing
`require_recent_mfa()` step-up. Reads require `privacy_governance.view`.

## DPO operational boundary

DPO privacy oversight does not grant operational Guidance access.

The DPO designation does not grant Counseling, Inventory, Referral, Exit Interview, Graduate Tracer,
Student Profiling report generation, Account Management, Platform Operations, or Organization
Management capabilities.

The DPO can see curated evidence that a significant authority/security/release event occurred without
receiving access to the underlying confidential content.

## Dedicated Privacy Governance domain

Add `compass.privacy_governance` with three persistence models only:

- `ProcessingActivity`
- `PrivacyReview`
- `PrivacyIncident`

No second audit/event table is introduced.

### Processing Activity

A Processing Activity documents institutional statements about how COMPASS processes categories of
personal information.

It stores bounded governance text, short constrained category lists, references, and active/retired
state. It stores no Student record samples, form submissions, uploaded datasets, or arbitrary nested
metadata.

The register starts empty. COMPASS does not seed invented legal bases, retention periods, approved
safeguards, or compliance conclusions.

There is deliberately no `is_compliant` flag. Compliance remains a human governance assessment.

Records may be retired but are not hard-deleted.

### Privacy Review / PIA record

A Privacy Review belongs to one Processing Activity and records one human privacy review or PIA
record.

The lifecycle is intentionally small:

- `OPEN`
- `RESOLVED`

Review type is either `PRIVACY_REVIEW` or `PIA`. Selecting `PIA` records how the institution
classified the review; COMPASS does not certify legal sufficiency.

Resolved reviews cannot be silently rewritten through the ordinary update operation. There is no
delete, reopen, generic approval workflow, reviewer-signoff engine, or file attachment.

### Privacy Incident

A Privacy Incident stores governance metadata about a suspected or confirmed privacy/security
incident. It is not a repository for leaked or affected data.

The lifecycle is forward-moving:

- `OPEN`
- `ASSESSING`
- `CONTAINED`
- `RESOLVED`

Notification assessment is human-entered:

- `NOT_ASSESSED`
- `NOT_REQUIRED`
- `REQUIRED`
- `COMPLETED`

COMPASS does not automatically determine whether an event is legally a breach, whether notification
is legally required, statutory deadlines, regulator content, or regulator submission.

No incident/review attachment facility is introduced.

## Governance auditing

Privacy-governance mutations reuse `audit.AuditEvent` and synchronous `record_event()`.

Stable actions are:

- `privacy.processing.created`
- `privacy.processing.updated`
- `privacy.processing.retired`
- `privacy.review.created`
- `privacy.review.updated`
- `privacy.review.resolved`
- `privacy.incident.created`
- `privacy.incident.updated`
- `privacy.incident.resolved`

Target types are:

- `privacy.processing`
- `privacy.review`
- `privacy.incident`

Mutation and successful audit append occur in one transaction. Audit failure rolls back the
governance mutation.

Audit metadata is limited to transition facts such as status, review type, changed field names, and
incident reference code. Complete governance narratives remain in their domain tables and are not
copied into audit metadata.

## Sensitive artifact release auditing

Add:

- `report.export_released`
- `document.download_released`

These actions mean COMPASS authorized and prepared/released the server response containing an
artifact. They do not prove that a browser completed a download or that the file was later opened,
copied, printed, emailed, transferred to USB, or otherwise handled outside the application.

Release auditing is explicit at the concrete release endpoints rather than generic
`Content-Disposition` middleware.

### Student Profiling

Instrument:

- `GET /api/v1/reports/student-profile/pdf`
- `GET /api/v1/reports/student-profile/xlsx`

The PDF/XLSX result carries a small safe release-context projection derived from the report already
built. No second report query is performed merely for audit.

The release AuditEvent target type is `reports.studentprofiling`, with the resolved Academic Year
UUID as its opaque target identifier.

Release metadata contains only report type, format, resolved Academic Year, optional Campus/College/
Program scope, and optional Year Level. It excludes aggregate values, demographic counts, Inventory
responses, and artifact bytes/content.

### Good Moral

Instrument:

- Student self certificate PDF release
- Counselor/GCO certificate PDF release

The audit target remains `goodmoral.request` with the request UUID.

Metadata contains only document type, variant, and access mode (`SELF` or `GCO`). It excludes
applicant identity, profile fields, receipt information, and certificate contents.

### Fail-closed release order

Sensitive release order is:

1. authorize;
2. resolve/build the domain artifact;
3. successfully render the artifact;
4. append the required release AuditEvent;
5. only then construct/return the artifact response.

Failed authorization or failed rendering does not create a successful release event.

If required release auditing fails, COMPASS returns a safe 503-class API error and does not return the
artifact bytes. Database exception details are not exposed.

## DPO Privacy & Security Activity

Add `GET /api/v1/privacy/activity` as a closed projection over `audit.AuditEvent`.

Categories are:

- `DATA_RELEASE`
- `ACCESS_CONTROL`
- `ACCOUNT_SECURITY`
- `PRIVACY_GOVERNANCE`

### Data release

Include only:

- `report.export_released`
- `document.download_released`

Present safe artifact type/format/scope and opaque resource references. Good Moral activity never
resolves the request into a Student identity.

### Access control

Curate:

- `account.enabled`
- `account.disabled`
- `account.role.changed`
- `account.designation.assigned`
- `account.designation.removed`
- `account.capability.override.set`
- `account.capability.override.removed`
- `account.mfa.reset`

Presenters allowlist only known safe metadata values.

DPO visibility of these changes is oversight and does not grant authority to perform Account
Management operations.

### Account security

Curate selected security-significant events:

- `auth.login.failed`
- `auth.mfa.totp.failed`
- `auth.mfa.totp.disabled`
- `auth.mfa.recovery.code.used`
- `auth.password.reset`

Failed login and MFA attempts are not attributed to the target account holder merely because an
AuditEvent is associated with a known account. Presenters use generic wording such as “Failed login
attempt for an account” and suppress actor display for those pre-authentication failures.

The projection does not return IP address, User-Agent, submitted email, credential material, OTP,
session IDs, recovery codes, or raw AuditEvent metadata.

Successful-login noise is intentionally excluded. This is not a SIEM.

### Privacy governance

Include only the nine privacy-domain mutation actions. Presentations do not copy complete review or
incident narratives.

Unrelated Appointment, Counseling, Inventory, Referral, Exit Interview, Graduate Tracer, Feedback,
and other ordinary domain AuditEvents are excluded unless a future requirement deliberately adds a
specific action.

There is no arbitrary action-filter endpoint and no global Audit Trail browser.

## API and input safety

Register the dedicated `privacy-governance` OpenAPI tag and `privacyGovernance` operation prefix
under `/api/v1/privacy`.

Request schemas reject unexpected fields. Governance text and references are bounded. Category
fields are bounded flat lists of short nonblank strings; arbitrary nested JSON is rejected.

Plain text is stored and returned as data; no HTML rendering/interpretation is introduced.

No hard-delete endpoint exists for Processing Activities, Reviews, or Incidents.

## Explicit non-goals

This foundation does not add:

- frontend dashboards/pages/components/charts/navigation;
- automatic compliance certification;
- automatic breach classification;
- statutory deadline automation;
- regulator integrations or regulator email;
- automatic retention/deletion;
- Right-to-Erasure automation;
- subject-access/bulk personal-data export;
- incident/review file attachments;
- DPO access to Counseling or other confidential domain contents;
- generic confidential-read auditing across every GET;
- raw/global Audit Trail browsing;
- SIEM functionality;
- DLP, device surveillance, USB monitoring, print tracking, or post-download tracking;
- backup/restore functionality.

## CI correction

The temporary one-test-only Runtime Operations debugging workflow accidentally present on the merged
base is not an acceptable permanent validation configuration.

This slice restores the canonical pre-PR #28 targeted test set, adds the Runtime Operations tests
introduced by PR #28, and adds Privacy Governance focused tests.

Temporary narrow rechecks may still be used after an isolated failure, but the checked-in workflow
must represent the canonical coverage before merge.

## Later expansion

ADR-061 adds versioned Privacy Notices, exact-revision acknowledgment, a human-readable Retention Policy register, a descriptive Processing Activity choice summary, and global Privacy Review discovery. Those later records do not change this ADR's DPO designation boundary or introduce automatic retention execution. Statements above describing three initial persistence models, nine initial privacy mutation actions, and excluded broader workflows describe the original foundation at the time it was accepted.
