# Institutional decision register — FAC-4

No institutional decision has been approved by this implementation or its tests.
This supplements the historical [FAC-2 register](../fac-2/policy-and-privacy.md).
Technical capabilities do not confer institutional approval.

| Decision | Institutional owner / required evidence | Implemented boundary | Live status |
|---|---|---|---|
| FAC-D1–D4 | GCO/UCN and identity/privacy authorities: Faculty eligibility, exact Student lookup, institutional form/digital submission and immutable authorship | Original FAC-2 providers unchanged; FAC-1 managed affiliation/capability ceiling retained | Unavailable pending approved adapters |
| FAC-D5 | GCO/UCN: actual acknowledgment responsibility, current Student College scope, digital receipt mapping to F3 `received_at`, wording and actor eligibility | Independent ACKNOWLEDGMENT provider, `EXPLICIT_RECEIPT_UCN_F3_V1`, actual actor/server time and transactional Audit | Provider returns None; positive synthetic fixtures only |
| FAC-D6 | GCO/privacy/UCN: administrative completion criteria, relevant obligations, authority, classification if needed and independent linked-task treatment | Independent CLOSURE provider, criteria evidence reference and strict explicit review; proposed `ADMINISTRATIVE_REVIEW_RETAIN_LINKS_V1` contract | Provider returns None; synthetic contract is a test proposal, not an institutional decision |
| FAC-D7 | GCO/privacy: three-state own projection and timestamp disclosure; void exceptions, historical read eligibility, retention and account eligibility changes | Independent FACULTY_TRACKING provider, `THREE_STAGE_TIMES_V1`; exact DTO allowlist; no actor/source/tasks; void omit/404 retained | New transition-bearing disclosure unavailable without evidence; no fabricated Submitted fallback |
| FAC-D8 | GCO/privacy/NOTIF: appropriate events/recipients/channels/content, stale semantics and disclosure | Inactive minimal intent contract, independent notice provider, no producers/catalog/delivery changes | None; no automatic Faculty/GCO/Student notices |

The proposed closure attestation records that the GCO actor reviewed the relevant
administrative obligations under approved criteria. It does not prove every task is
complete. No closure narrative/classification is collected because no actual institutional
requirement for one is established. FAC-5 must record and review any different criteria
or required minimal classification before adapting the contract.

Approval adapters must be reviewed code backed by actual decision evidence, not an
environment switch, raw GRANT, arbitrary Audit record or developer override. Evidence
must define actor/role/College admission, validity, semantics and disclosure separately.
The positive test fixture seals evidence in a disposable database and monkeypatches
providers only within a test process. It cannot activate application defaults.
