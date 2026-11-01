# FAC-5 — integration assurance and institutional UAT preparation

Base: integration `d9971e89`, after merged FAC-1 #348 through FAC-4 #351.
Target: `integration/ux15-modernization`. No deployment, staging/main promotion,
institutional policy adapter or automatic Student Referral notice is introduced.

The work fixes actionable inherited CI defects, preserves the canonical Faculty/GCO
security and migration boundaries, expands integrated responsive/privacy assurance and
prepares an unsigned institutional decision/UAT/operations package.

- [Verified baseline and bounded decisions](preflight.md)
- [CI failure causes and corrections](ci-failures.md)
- [Validation, reproduction and exact-head gate rules](validation.md)
- [Security/privacy assurance](security-and-privacy.md)
- [Institutional FAC-D1–D10 decision packet](institutional-decisions.md)
- [UAT scripts, roles and issue reporting](uat.md)
- [Deployment compatibility and recovery checklist](operations-and-recovery.md)
- [Readiness verdicts and remaining owners](readiness.md)
- [Safe local evidence](evidence/)

**Technically validated where demonstrated; institutional activation and deployment
remain blocked pending the specified approvals.** Actual policy providers remain None.
Synthetic positive scenarios are not institutional approval, human UAT or live availability.
Exact-SHA hosted run links, complete job outcomes and the final gate assessment are
recorded in the implementation PR; focused local results do not replace those gates.
