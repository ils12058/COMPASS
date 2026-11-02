# Faculty integration authorization and privacy assurance

The Faculty capability ceiling remains exactly `referrals.submit_self` and
`referrals.view_submitted_self`. No role/designation, raw override or home College
can grant Faculty GCO, clinical, Student-self-service, directory or IT authority.
Application providers remain None and no activation flag/endpoint/adapter is added.

The consolidated assurance test uses actual opaque sessions and CSRF with CAS Faculty,
CCMS Student and CCMS Counselor, then verifies encrypted canonical commit, saved College/
submitter/time provenance, annual reference allocation, explicit actual actor/time receipt
and closure, exact seven-field owned projection and unchanged source/counter on canonical
replay. It also checks another Faculty owner and a different College GCO actor.

Twenty direct API boundary cases cover GCO Referral list/selector/detail/PDF/administration,
Call Slip operational/self records, Follow-Ups, Counseling/continuity, E-Counseling, Assessment
records/Student selection and administrative account APIs. Malformed raw broad grants remain
ineffective. E-Counseling uses a real synthetic Appointment shown readable to its authorized
Counselor before testing Faculty denial; an unrelated missing UUID is not used as access proof.

Existing FAC-1–4 suites retain current role/activity/session/home/supervision/Student placement,
policy withdrawal/expiry, confirmation expiry, ownership, strict payload, transactional Audit,
idempotency, annual counter, concurrent transitions/void, historical source/PDF and linked-work
checks. Faculty never receives the internal GCO detail DTO or decrypts its source for own reads.

## Client state and disclosure review

- `faculty-referrals/use-submission.ts`: identifier, reason, confirmation and intended body/key
  stay in component memory; confirmation/submission mutations have no sensitive variables or
  returned cache payload and use zero garbage-collection lifetime. No persistent draft, URL or
  analytics copy exists. Explicit exact retry preserves one uncertain intent.
- `portal-boundary.tsx`: account changes cancel/remove protected queries before the next account
  mounts. Confirmed sign-out clears the client; the session projection gates the account-owned
  cache. Current policy/session checks remain authoritative on every read/write.
- `faculty-referrals/records.tsx`: owned safe projection only. Source reason, GCO actor, Actions,
  Call Slips, Follow-Ups, contact and clinical data are absent. Authorization errors conceal data;
  transition-bearing disclosure cannot fall back to a false Submitted state.
- `faculty_services.py` and `administration.py`: synchronous content-free Audit and transactional
  provenance. Integration assurance checks that the synthetic reason and confirmation are absent
  from target Audit metadata. Existing FAC-2/4 tests retain strict DTO/audit field checks.
- `notification_contract.py`: an explicitly inactive intent, current authenticated submitting
  Faculty eligibility, actual event/time, minimal reference/route and stable event identity. No
  live catalog, producer, channel or automatic Student notice is added. Future delivery needs
  approved current-recipient/event checks and existing trusted-origin/idempotency machinery.
- Browser suites assert no protected endpoint probing from Faculty screens, no confidential input
  in storage/URLs, safe diagnostic copy, correct account/role routes and preserved uncertain state.
  Screenshots/result reports use synthetic identities only. Requests remain in test memory;
  committed reports contain safe case names/results rather than request bodies or session cookies.

The session Role join removes an extra database read; it removes no permission/role/source or
privacy check. Summary regeneration retains Encounter locking and encryption. The Case Coverage
revocation inventory exception is model-bound and rejects any additional writer; it does not
redirect AuthSession revocation or bypass socket closure. The recovery rehearsal preserves all
irreversible migration/history boundaries.

No real institutional participant, production grant inventory, live retention decision, external
Notification delivery or deployed storage/key configuration is claimed reviewed. Actual approved
recipient/disclosure policy, physical-device/screen-reader UAT and controlled staging rehearsal
remain distinct institutional/operational work.
