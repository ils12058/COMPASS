# FAC-4 — explicit GCO administration and Faculty-safe tracking

Implementation target: `integration/ux15-modernization`, after FAC-1 #348, FAC-2 #349,
and FAC-3 #350. This slice creates a reviewable PR; it does not merge, deploy or
activate institutional policy.

- [Decisions recorded before schema changes](decisions.md)
- [Architecture and API/exception contracts](architecture.md)
- [Institutional decision register](policy-register.md)
- [Validation and screenshots](validation.md)
- [FAC-5 release/UAT handoff](handoff.md)

The canonical Referral derives Submitted, Received by GCO and Administratively
Closed from persisted transition facts. Actual live policy providers remain unavailable.
Positive transition/disclosure evidence is confined to isolated synthetic tests.
Notifications have an inactive candidate-intent contract only.
