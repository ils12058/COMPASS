# ADR-032: Student lifecycle and former-student access

## Status

Accepted for the Student lifecycle foundation.

## Context

COMPASS needs to distinguish a Student's present eligibility for current-student workflows from
the account's operational identity and from ownership of historical records. Graduation or leaving
the institution must not require a second account or an ALUMNI primary role.

## Decision

The canonical primary role remains `STUDENT`. Accounts add one nullable typed
`student_lifecycle_status` with exactly `CURRENT`, `GRADUATED`, and `FORMER`.

`FORMER` is deliberately neutral: it means the account is no longer treated as current and COMPASS
does not have confirmed graduation for this classification. It does not mean dropped, transferred,
dismissed, failed, expelled, or any other inferred reason.

Existing Student accounts are deterministically migrated to `CURRENT`. The canonical user manager
initializes newly created Student accounts to `CURRENT`; accounts that have never been Students may
remain null. Role transitions preserve any existing lifecycle value. Switching into `STUDENT` with
no prior lifecycle initializes `CURRENT`; switching away does not manufacture `GRADUATED` or
`FORMER`.

Lifecycle changes use Account Management's existing `accounts.manage` authority and recent-MFA
requirement. COMPASS records an institutionally established classification; it does not determine
whether academic graduation occurred. The mutation is row-locked, no-op safe, audited as
`account.student_lifecycle.changed`, and does not revoke sessions or disable the account.

Role capabilities are unchanged. Lifecycle is an additional domain eligibility condition, enforced
only at current-student initiation or mutation boundaries. Historical ownership continues to use the
same User UUID.

## Domain boundaries

- Inventory current-year ensure/update/submit require `CURRENT`; history reads remain available.
- New Student Appointment creation and booking counselor discovery require `CURRENT`; own existing
  Appointment reads and cancellation remain available.
- Counseling Encounter creation remains lifecycle-neutral so actual institutional interactions can
  still be recorded.
- New Routine Interview creation and Student intake mutation require `CURRENT`; historical Student
  reads and Counselor completion of an existing record remain available.
- Exit Interview initiation, Student edit, submission/resubmission, and Head reopen-for-Student-
  correction require `CURRENT`; historical reads remain available. Initiation continues to bind the
  Academic Year from the canonical submitted Inventory resolver rather than resolving a second
  independent current-year prerequisite.
- E-Counseling Student workspace reads and consent reads remain available. Student join and approval
  of pending consent require `CURRENT`. Denial and withdrawal remain available for safety/privacy
  cleanup. Counselor-side workspace, consent request, media control, and recording behavior are not
  lifecycle-gated in this slice.
- Account login, password, MFA, trusted sessions, profile/profile photo, My Activity/Security
  Activity, and StudentAffiliation are unchanged.

## Deferred work

No enrollment model, Registrar integration, generic eligibility engine, Good Moral implementation,
Graduate Tracer, lifecycle history table, or ALUMNI role is introduced.

Future Good Moral eligibility remains straightforward: F4 Current Student Good Moral can require
`CURRENT` plus the current submitted Inventory; F6 Graduate Good Moral can require `GRADUATED`
without a current Inventory prerequisite. `FORMER` alone does not imply graduate-certificate
eligibility. Graduate Tracer remains deferred and may reuse `GRADUATED` as an eligibility signal.
