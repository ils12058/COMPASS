# Faculty and GCO UAT execution package

Prepared for institutional review; **no institutional UAT or participant sign-off is claimed**.
Use synthetic identities and disposable records. Real Student identity/narrative use requires
separate appropriate authorization. Physical-device and actual screen-reader sessions remain
outstanding. Automated keyboard/status semantics are supporting evidence only.

## Environments and participants

**D — unavailable default:** normal code with all actual providers returning None. Provisioning,
Home/navigation, denial/privacy and historical GCO workflows can be assessed. Expected denial
is a passing result; do not add flags, GRANTs or Audit rows to make a positive form appear.

**S — isolated positive synthetic environment:** an engineer-owned disposable PostgreSQL fixture
with explicit synthetic policies patched only in that test process. This is suitable for testing
positive mechanics, not demonstrating institutional authorization. No deployment image or live
provider receives these fixtures. Approval withdrawal/expiry cases require controlled test setup.

| Participant role | Synthetic identity/authority | Purpose |
|---|---|---|
| Account manager | Existing authorized manager, recent MFA, separate target | Faculty provisioning/home/version conflicts |
| CAS Faculty A | Managed active CAS home; two narrow capabilities | Submitter and own tracking |
| CAS Faculty B | Different actual account | Foreign ownership denial |
| CCMS Student | Active exact institutional identity/current placement | Referred subject; no automatic notice |
| CCMS Counselor | Actual CCMS responsibility | Appropriate GCO receipt/closure |
| CAS Counselor | Different College responsibility | Out-of-scope denial |
| GSS | Current CCMS supervision, plus unsupervised variant | Supervision and current authority |
| GCO/process, privacy/records, accessibility observers | Review authority; no expanded confidential account permissions | Meaning, privacy, usability and issue adjudication |
| Technical facilitator | Disposable fixture control only | Controlled lost responses, expiry, scope/policy changes and safe evidence |

## Scripts and pass/fail criteria

Record environment, participant role, browser/device/text setting, step result, expected/actual
behavior and safe issue ID for each scenario. A blocked/unavailable precondition is not an
executed positive scenario. Never label a simulated approval as institutionally approved.

| ID / environment | Steps | Expected result and pass/fail boundary |
|---|---|---|
| U01 / D,S | Manager creates a separate Faculty account, assigns active CAS College with current version/basis; try stale version or inactive parent | Correct single role/home/Campus, actual manager Audit; stale/inactive assignment refused; no GCO/IT authority appears |
| U02 / D,S | Faculty opens Home, palette/navigation, Profile and My Referrals | Correct managed home and own account destinations. D shows unavailable service; S advertises only separately current allowed functions. No fake totals |
| U03 / S; D denial | Enter one exact CCMS Student ID; try absent, inactive, wrong-role, unplaced and prefix values | Approved minimum display-name confirmation only; indistinguishable negative facts. D returns unavailable without directory disclosure |
| U04 / S | CAS Faculty refers confirmed CCMS Student | Student College remains CCMS; home remains CAS provenance. Only Student College responsibility governs GCO intake |
| U05 / S | Enter synthetic course/reason, review, cancel/edit and submit once; use keyboard | Labels/errors/focus preserve input. Actual committed source uses authenticated Faculty/server facts, existing encrypted form and reference; no invented signature |
| U06 / S | Open result and My Referrals after commit | Same reference/original time and real Submitted fact; no acknowledgment or clinical implication; approved page/has_next only |
| U07 / S; D denial | CCMS Counselor or supervised GSS reviews intake and explicitly acknowledges; CAS Counselor/unsupervised GSS tries | Actual authorized actor/time/version and Audit; prior Submitted becomes Received only after commit. Wrong scope/authority denied. D offers no action |
| U08 / S; D denial | Try closure before receipt, then review obligations and explicitly close under test policy | Prior receipt required, strict review, actual closer/time and independent Audit; no clinical resolution or linked-task completion inferred. D action unavailable |
| U09 / S | Faculty refreshes Home/list/detail through all three states and approved timestamps; open closure Help | Only persisted facts/approved times; no GCO actor, reason, notes, tasks or clinical details. No speculative completed milestones |
| U10 / D,S | Faculty B opens A's UUID; Faculty tries GCO detail/PDF/actions, Call Slips, Follow-Ups, Counseling/E-Counseling, assessments, directory and admin routes/APIs | Safe denial/404 per owning contract, no confidential payload or protected component/query mount. Raw privilege drift cannot cross the Faculty ceiling |
| U11 / D,S | Withdraw an isolated approval; deny current read/action policy; lose connection during loading | Truthful unavailable/error; no action is authorized by stale availability or own-list success. Transition-bearing reads never falsely become Submitted |
| U12 / D,S | Revoke/expire session or change role/activity/home/Student placement while pages/dialogs are open | Current server eligibility rechecked; stale/denied actions do not mutate, leak or auto-replay. Changed placement does not rewrite saved provenance |
| U13 / S | Let submission commit but drop its response; have GCO acknowledge; deliberately retry exact original intent | No automatic retry or editing into another intent. Identical key/body returns canonical 200 with same record/reference and current Received state; no duplicate/counter/Audit |
| U14 / D,S | Authorized GCO reads/reprints a synthetic historical paper Referral with original receipt and saved revision | Original source/ciphertext/provenance/date/PDF remain correct; no invented Faculty ownership or acknowledgment actor |
| U15 / D,S | GCO reviews linked pending/completed confidential Follow-Ups and active/completed/voided Call Slips around explicit closure/void | Independent linked work/history and GCO scope unchanged. Existing active/completed Call Slip void restrictions still apply; Faculty sees none |
| U16 / S | Two actors acknowledge; stale closure; race acknowledgment/closure with void in both orders | One valid event per transition; defined conflict/review recovery, no contradictory facts. Void retains history and Faculty omit/404 |
| U17 / D,S | Inspect notification/storage/cache/error/Audit evidence using synthetic data | No automatic Student Referral notice, no live administrative notice producer, no reason/token in storage/URLs/Audit/external messages. Account change clears owned caches |

## Accessibility and connection runs

Run U02–U09/U11/U13 in Chromium and WebKit at 320, 390, 768, 1024 and 1440px, normal
and 200% text, light/dark OS preference and reduced motion. Include long synthetic names
and valid references, keyboard-only entry/review/cancel, labeled controls/status announcements,
focus restoration, slow reads, empty pages, initial errors, background refresh failure and lost
responses. Preserve the intended light application palette. Confirm actions and the actual
record fit available width; scrolling vertically is expected for enlarged long content.

A facilitator should run actual screen-reader checks (focus order, dialog naming/description,
status announcements, form errors and concealed data), plus physical phone/tablet checks before
institutional sign-off. Record device/OS/assistive-technology versions and observations; leave
results unexecuted until those sessions actually happen.

## Issue reporting and sign-off

For each issue record UAT ID, environment/build SHA, role, reproduction, expected/actual result,
impact, browser/viewport/text settings, safe screenshot/log reference and owner. Do not paste a
real Student ID, reason, confirmation value, cookie, key or confidential clinical/task detail.
Privacy leak, unauthorized mutation, contradictory provenance or duplicate consequential write
blocks technical acceptance immediately. Separate availability by policy from a technical defect.

Pass/fail/not-run/blocked are distinct. Participants provide actual review/sign-off outside this
unsigned package. Technical, institutional policy, UAT and deployment decisions remain separate.
