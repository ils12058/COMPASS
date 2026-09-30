# ADR-070: Capability dependency composition

## Status

Accepted.

## Context

COMPASS uses roles and institutional designations to provide baseline capability grants, with
per-account capability overrides for exceptional authority changes. Resource scope, domain
lifecycle eligibility, and recent MFA remain separate authorization dimensions.

Before this decision, effective capability computation combined baseline grants with active
GRANT overrides and removed active REVOKE overrides, but it did not express prerequisites
between capabilities. This allowed contradictory effective states such as management authority
remaining effective while the read capability required by the same product workflow had been
revoked.

## Decision

Capability dependencies are version-controlled policy in `accounts/policy.py`.

A dependency means:

```text
A requires B
```

and therefore A may be effective only while B is effective.

Dependencies do not grant B. They only constrain authority already present through role,
designation, or explicit GRANT override.

The effective-authority pipeline is:

```text
role grants
+ designation grants
+ active GRANT overrides
- active REVOKE overrides
→ canonical filtering
→ dependency resolution to a fixed point
```

Explicit REVOKE remains authoritative. If a prerequisite is revoked, dependent capabilities are
suppressed. The underlying role/designation grant or override remains persisted and can become
effective again if the prerequisite later becomes effective.

The canonical dependency policy is:

```text
routine_interviews.manage_self     → routine_interviews.view_self
routine_interviews.manage_assigned → routine_interviews.view_assigned
exit_interviews.manage_self        → exit_interviews.view_self
exit_interviews.reopen             → exit_interviews.view
graduate_tracer.manage_self        → graduate_tracer.view_self
good_moral.request_self            → good_moral.view_self
good_moral.manage                  → good_moral.view
good_moral.issue                   → good_moral.view
counseling.manage_assigned         → counseling.view_assigned
referrals.manage                   → referrals.view
call_slips.manage                  → call_slips.view
availability.manage_self           → availability.view
privacy_governance.manage          → privacy_governance.view
platform_operations.manage         → platform_operations.view
```

The dependency graph is validated as canonical, non-self-referential, and acyclic. Normal
role/designation baseline combinations are also validated for dependency coherence.

Account access inspection exposes each capability's direct requirements and any requirements
missing from projected policy composition. Baseline source provenance and actual persisted
overrides remain separate fields.

New administrative GRANT overrides for a dependent capability are rejected when its prerequisite
authority is unavailable. Prerequisites are never granted automatically. REVOKE of a prerequisite
is allowed because it is a least-privilege reduction.

Runtime inactive or unauthenticated accounts still have no effective capabilities. Account
administration may separately evaluate projected policy composition so a coherent future
configuration can be prepared for an inactive account without weakening runtime access rules.

## Consequences

- Existing domain guards continue asking only for their action capability; central resolution
  guarantees audited dependent capabilities cannot be effective without their prerequisites.
- Authentication session payloads remain compact and expose only final effective capability codes.
- Historical incompatible overrides remain recorded for administrative provenance but cannot
  produce incoherent effective authority.
- Override expiry automatically changes dependency resolution at evaluation time; no background
  cleanup job is required.
- Resource scope, ownership, domain eligibility, and recent MFA behavior are unchanged.
- No database schema or override data migration is introduced.
- Phase 6B remains responsible for operational-domain frontend cleanup made unreachable by the new
  invariant.
- Phase 6C remains responsible for actor-action presentation issues such as read-only Platform
  users seeing management actions.

## Alternatives rejected

### Silently grant prerequisites

Rejected because granting a dependent capability must not manufacture additional authority that
an administrator did not explicitly approve.

### Automatically persist dependent REVOKEs

Rejected because dependency suppression is derived effective truth. Rewriting role grants or
creating extra override rows would corrupt administrative provenance and make restoration
semantics harder to reason about.

### Enforce every manage/view pair in each domain

Rejected because it duplicates policy, risks drift between domains, and does not protect session
capability output or other consumers of the central resolver.

### Infer dependencies from capability naming

Rejected because not every management capability requires the similarly named view capability.
Dependencies are added only where an actual workflow invariant has been established.
