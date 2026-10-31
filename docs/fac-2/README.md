# FAC-2 secure Faculty Referral backend

FAC-2 implements working backend services and strict APIs for exact Student
confirmation, digital Faculty submission, and minimal own-submission reads. Positive
tests exercise the complete transaction under explicit synthetic approved policies.
**No institutional policy is installed:** both real policy providers return `None`,
so these operations deny access. Capabilities and an approved paper form are not
authority to activate digital submission or disclose Student identities.

Read [preflight](preflight.md), [architecture and migration](architecture.md),
[privacy and policy decisions](policy-and-privacy.md), [FAC-3/FAC-4 handoff](handoff.md)
and [validation](validation.md).

## Implemented API

All routes use the existing opaque session cookie. Unsafe requests require existing
Django CSRF bootstrap/header handling. They do not accept a bearer token or a client
actor identity. Faculty confirmation is a separate purpose-bound signed value,
never a sign-in credential.

| Method/path | Operation ID | Function authority |
| --- | --- | --- |
| `POST /api/v1/faculty/referrals/student-confirmation` | `referralsFacultyConfirmStudent` | `referrals.submit_self` plus approved lookup policy |
| `POST /api/v1/faculty/referrals` | `referralsFacultySubmit` | `referrals.submit_self` plus approved digital form/eligibility and current lookup policy |
| `GET /api/v1/faculty/referrals` | `referralsFacultyListMine` | `referrals.view_submitted_self` plus approved own projection |
| `GET /api/v1/faculty/referrals/{referral_id}` | `referralsFacultyGetMine` | Same, with immutable submitter ownership |

The live authenticated Faculty actor, account activity, actual unrevoked/unexpired
session and required effective capability are reloaded for every operation. Current
institutional home must be usable under the implemented policy contract. Defaults
grant only the two new Faculty capabilities; submission depends on own-read. The
FAC-1 ceiling now admits exactly those two functions and still rejects all GCO,
clinical, Student-self-service and administrator grants. Other roles cannot acquire
the new Faculty functions, including through malformed persisted GRANTs.

These four routes are independent of the existing GCO APIs. There is no Faculty
PDF, directory search, internal Referral DTO, reason readback, action, Follow-Up,
Appointment, acknowledgment, closure or Notification endpoint here.

## Request and response examples — synthetic, not activation evidence

Student confirmation request:

```json
{"institutional_id":"SYNTHETIC-STUDENT-001"}
```

An authorized positive response contains only `confirmed`, Student `display_name`,
an opaque-to-UI `confirmation` string, and `expires_at`. All eligible negative
identity/placement cases return the same shape:

```json
{"confirmed":false,"student":null,"confirmation":null,"expires_at":null}
```

Submission requires `Idempotency-Key` and a strict body with exactly these fields:

```json
{
  "confirmation":"purpose-bound-confirmation-from-the-server",
  "course_year_block":"Faculty-supplied Course/Yr & Blk",
  "reason":"Confidential source-form reason"
}
```

`course_year_block` is declared form text, not verified academic placement. The
Student's College always comes from the placement resolver, never from this text
or Faculty home. Faculty name, date/time, source channel, form revision, identities,
College provenance, reference and approval evidence are server-derived.

Successful creation returns 201; an identical authorized replay returns 200:

```json
{
  "id":"00000000-0000-4000-8000-000000000001",
  "reference_code":"REF-2026-000001",
  "submitted_at":"2026-10-31T12:00:00Z",
  "state":"SUBMITTED",
  "student":{"display_name":"Synthetic Student"}
}
```

Own list uses canonical `items`, `page`, `page_size`, `has_next`; no totals are
invented. Own details have the identical allowlisted projection. Confidential
content is never decrypted for these responses. Another submitter's UUID, an
unknown record, a GCO/paper record or an internally voided submission returns 404
from the own-detail service. Lists omit voided records until an approved exceptional
Faculty projection exists. `SUBMITTED` records a real committed submission; it does
not mean receipt, processing, care, approval or administrative closure.

The canonical wire contract is `contracts/openapi.json`; Orval regeneration supplies
FAC-3's types, operations and query keys. Frontend generated output remains ignored.
FAC-1's holding page is retained and does not advertise an available workflow.
