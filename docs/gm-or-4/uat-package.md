# Future institutional UAT package

**Every scenario below is NOT EXECUTED institutionally.** Automated synthetic evidence does not mark these scripts passed. Use only an institutionally approved UAT environment/accounts/data and separately authorized policies/grants/cutover. No deployment or real receipt inspection is authorized by this document.

Required participants: authorized Student testers for F4/F6, GSS recorder, approved personal inspector, Counselor final issuer, GCO supervisor, Cashier numbering/fee representative, Registrar representative for external dry seal, named release/data operator, privacy custodian and accessibility/device testers. One person may hold multiple approved duties; no invented two-person inspection rule is imposed.

Before testing, pin candidate/backend/frontend/worker/contract/schema versions, approve test data custody and retention, fee definitions/applicability and named grants; reconcile the approved legacy fixture inventory and prepare recovery/pause controls. Record each result PASS/FAIL/BLOCKED with actual execution time, actor, version and protected evidence location. Keep real Student/payment details out of public screenshots/PRs.

| # | Scenario | Participant/precondition | Script and expected result | Evidence checklist | Institutional status |
| --- | --- | --- | --- | --- | --- |
| 1 | F4 receipt-free request | Eligible CURRENT Student with submitted Inventory/required Exit Interview | Request without receipt fields; approved success and owned pending detail | Receipt-free submitted payload and owned request | NOT EXECUTED |
| 2 | F6 receipt-free request | Eligible Student with claimed degree/date | Request without OR/payment fields; preserve qualification limitations | Receipt-free request and claim snapshot | NOT EXECUTED |
| 3 | Cashier/GCO guidance | Student with pending F4/F6 | Separate OR per request, external Cashier then physical GCO presentation, no invented approved fee | Student-safe screen and reviewed copy | NOT EXECUTED |
| 4 | GSS receipt entry | Approved GSS; synthetic or separately authorized receipt | Save exact printed facts; no inspection appears automatically | Saved number/date/actual amount, claim revision, no inspection | NOT EXECUTED |
| 5 | Authorized physical inspection | Explicit approved inspector; exact saved receipt | Unchecked personal assertion; server actor/time; no Cashier-cleared claim | Named inspector, policy and exact revision evidence | NOT EXECUTED |
| 6 | Unauthorized verification denial | GSS without grant; IT; Head without grant; Student | Direct API denial and no receipt/evidence/Audit/payment mutation | Before/after protected comparisons and refusal code | NOT EXECUTED |
| 7 | Missing receipt | Pending eligible request | Cannot inspect/prepare/issue under approved ACTIVE | Missing blocker, unchanged facts | NOT EXECUTED |
| 8 | Incomplete receipt | Missing date or amount | Retain draft; block consequential transition | Incomplete blocker and preserved draft | NOT EXECUTED |
| 9 | Duplicate receipt | Other Student/variant/cancelled or superseded key | Safe conflict without other-Student detail; permanent reservation | Refusal and restricted reservation review | NOT EXECUTED |
| 10 | Wrong amount | Approved expected 80; actual 0/75/100 where sanctioned test fixture | Keep actual value, block eligibility, follow approved escalation | Actual vs expected and preserved facts | NOT EXECUTED |
| 11 | Unknown fee applicability | Receipt outside approved coverage or no schedule | Policy unresolved, no fallback/invented date | Refusal and applicable authority gap | NOT EXECUTED |
| 12 | Correction/reinspection | Verified/prepared request, authorized clerical correction | Old inspection retained/invalidated, old number reserved; new intentional inspection and preparation | Revision chain, original actor/time, new evidence | NOT EXECUTED |
| 13 | Unrelated correction | Verified/prepared request, certificate-only change | Same receipt inspection retained; return to preparation | Unchanged inspection and new preparation review | NOT EXECUTED |
| 14 | Counselor issuance | Fresh READY request and correct reviewed tokens | Only authorized Counselor issues once; notification/feedback exactly once | Issued form/template/issuer/claim/inspection references | NOT EXECUTED |
| 15 | Historical PDF/reprint | F4/F6 issued with blank/non-80/duplicate legacy OR | Authorized unchanged historical document and user-initiated native print; no reissue | PDF/paper comparison and issuance-event count | NOT EXECUTED |
| 16 | Cancelled number non-reuse | Cancelled request with reserved OR | Other request cannot use identifier; historical facts remain | Permanent reservation/refusal | NOT EXECUTED |
| 17 | Legacy duplicate review | Approved protected duplicate inventory | No arbitrary owner, no fake former identifier/inspection; governed disposition only | Restricted case review and approved decision | NOT EXECUTED |
| 18 | Interrupted workflow/retry | Controlled network loss before/after commit; stale second actor | Read canonical state, no automatic verification/issue replay; explicit review or exact committed acknowledgment | Operation identity, before/after rows/outcomes and recovery record | NOT EXECUTED |

## Human accessibility, printing and release

Use real keyboard-only navigation, actual screen reader, native 200% browser zoom and supported touch device. Record checkbox announcement, focus containment/restoration, disabled/pending/success/error announcements, long-value wrapping and small-screen usability. Run supported Chromium/WebKit native print dialogs, verify actual F4/F6 paper/receipt/issuer/date/form version, obtain physical signature/release and observe the Registrar dry-seal handoff. None of these is covered by headless print instrumentation or root text scaling.

Acceptance requires resolved critical failures, protected evidence review and actual named institutional sign-off. A script may remain BLOCKED without fabricating an exception. Test completion does not itself approve deployment or ACTIVE cutover; release/activation authority is separate.
