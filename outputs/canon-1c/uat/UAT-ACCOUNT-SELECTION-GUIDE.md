# UAT Account Selection Guide

COMPASS Staging Dataset v1 (dataset version 1). Generated 2026-10-17T06:59:47+08:00 by `seed_staging_dataset report` from the manifest and a passing read-only verification of the live-staging database. Do not edit by hand: change `be/compass/staging_seed/` and regenerate.

All names, identifiers, addresses and email addresses are synthetic. This document contains no passwords, MFA secrets, tokens, confidential form answers or counseling content, and no evaluator identities.

How to choose seeded accounts for stakeholder UAT. Recommendations follow the scenario matrix; the account catalog lists every account.

## Rules for every assignment

- Assign each UAT-ready account to **one** evaluator. Mutating scenarios change the account's state, and a rerun of the seeder never restores a consumed state.
- Never assign background accounts as delivered; they populate rosters and reports. To use one, add it to the manifest as a participant and regenerate.
- Restricted accounts are for negative-authorization tests only. Disabled accounts cannot receive credentials; the others need `issue-credentials --account <key>`.
- Record assignments only in the private copy of `UAT-ACCOUNT-ASSIGNMENT-TEMPLATE.csv`; never commit evaluator names or contact details.
- Credentials are delivered privately from the protected handoff file; this guide and the catalog never contain them.

## Proposed 40-person allocation

Each key below belongs to a different participant. Alumni use the STUDENT role with GRADUATED lifecycle; ITSO personnel use IT_ADMIN. This is a selection proposal, not authorization to issue credentials. No background or onboarding account is included.

| Participant category | Count | Exact account keys |
| --- | --- | --- |
| Head Guidance Counselor | 1 | `head_guidance` |
| Guidance Counselor | 3 | `counselor_a`, `counselor_b`, `counselor_c` |
| Guidance Services Staff | 2 | `gss_a`, `gss_b` |
| Current Student | 25 | `first_year`, `second_year`, `ar_01`, `ar_02`, `ar_03`, `ar_04`, `ar_05`, `ar_06`, `ar_07`, `ar_08`, `ar_09`, `ar_10`, `ar_11`, `ar_12`, `ar_14`, `ar_15`, `ar_16`, `ar_17`, `ar_18`, `ar_19`, `ar_20`, `ar_21`, `ar_22`, `ar_23`, `ar_24` |
| Alumni | 5 | `recent_graduate`, `alumni`, `ar_13`, `ar_25`, `ar_26` |
| ITSO personnel | 3 | `it_admin`, `it_admin_2`, `it_admin_3` |
| Data Protection Officer | 1 | `dpo` |

Keep one evaluator per account. Confirm mailbox ownership and staff authenticator enrollment before issuance; record actual assignments only in the private template. The template also lists reserve accounts; only the 40 keys above form this allocation.

## Student

Give each Student evaluator their own action-ready or rich account. Action-ready accounts (`ar_…`) each start from one pending action, so two evaluators never need the same Student. Rich accounts carry multi-domain history for exploratory testing.

| Account | ID | Why recommended | Assignable | Scenarios | Initial state changes? | What it starts with | Conflicts / limitations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| first_year | STG-S-0001 | Current first-year Student (upcoming online session) | UAT-ready (assignable) | STU-RI-02 | Yes — state changes | Submitted Inventory (4Ps household), a cancelled booking and an upcoming ONLINE Counseling Appointment whose Routine Interview intake is a draft. | — |
| second_year | STG-S-0002 | Current second-year Student (completed counseling) | UAT-ready (assignable) | STU-INV-03 STU-NOT-01 | Yes — state changes | Two annual Inventories; completed session with finalized Routine evaluation and a published Shared Summary; scheduled follow-up; a withdrawn Call Slip; feedback. | — |
| referred | STG-S-0003 | Current third-year Student (referred) | UAT-ready (assignable) | STU-HIS-01 | No — read-only | Program Chair referral (plus a voided duplicate), Call Slip interview, REFERRED Encounter, Routine Interview awaiting evaluation, published follow-up summary. | — |
| fourth_year | STG-S-0004 | Current fourth-year Student (walk-in and no-show) | UAT-ready (assignable) | STU-SUM-02 | No — read-only | Last year's referral by departed staff, a no-show, a walk-in Encounter with a finalized Routine Interview and an unpublished Shared Summary draft, a follow-up. | — |
| graduating | STG-S-0005 | Current graduating Student (Exit Interview draft) | UAT-ready (assignable) | STU-EXIT-03 | Yes — state changes | Delayed final year: Exit Interview draft, pending Good Moral request and a career consultation booked with the Head Guidance Counselor. | — |
| recent_graduate | STG-S-0006 | Recent graduate (June 2026) | UAT-ready (assignable) | STU-GT-02 | Yes — state changes | Historical Inventories and Exit Interview, issued graduate certificate, Tracer draft. | Graduated: no current College affiliation or current-year Inventory. |
| alumni | STG-S-0007 | Alumna (June 2025) | UAT-ready (assignable) | STU-GM-04 | No — read-only | Historical Inventory and Exit Interview, submitted Tracer, pending graduate request. | Graduated: no current College affiliation or current-year Inventory. |
| former | STG-S-0008 | Former Student (transferred out) | UAT-ready (assignable) | STU-APT-05 | No — read-only | One historical Inventory, then FORMER: a working account with limited workflows. | Former Student: excluded from current operational pickers and rosters. |
| onboarding | STG-S-0009 | Onboarding Student (never signed in) | UAT-ready (assignable) | STU-ONB-01 | Yes — state changes | Provisioned account that has never signed in: first-time Password Access onboarding. | Needs an operator-controlled mailbox (STAGING_SEED_ONBOARDING_EMAIL) for the one-time code; no credential is issued for it. |
| active_referral | STG-S-0010 | Current second-year Student (active referral) | UAT-ready (assignable) | STU-INV-04 | Yes — state changes | Inventory draft, a new adviser referral and a Call Slip issued live by gss_a. | — |
| good_moral | STG-S-0011 | Current third-year Student (issued certificate) | UAT-ready (assignable) | STU-GM-03 | No — read-only | Issued, printable current-Student Good Moral certificate and a cancelled duplicate. | — |
| ar_01 | STG-S-0101 | Ready to book a first Counseling session | UAT-ready (assignable) | STU-APT-01 NEG-05 | Yes — state changes | Submitted Inventory and no Appointment: books Counseling with counselor_a. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_02 | STG-S-0102 | Ready to book a first Counseling session | UAT-ready (assignable) | STU-PRF-01 STU-APT-02 STU-PUB-01 PND-SVC-01 | Yes — state changes | Submitted Inventory and no Appointment: books Counseling with counselor_b. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_03 | STG-S-0103 | Upcoming in-person session to reschedule | UAT-ready (assignable) | STU-APT-03 PND-REM-01 | Yes — state changes | Upcoming in-person Appointment with counselor_a that can be rescheduled. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_04 | STG-S-0104 | Upcoming in-person session to cancel | UAT-ready (assignable) | STU-APT-04 | Yes — state changes | Upcoming in-person Appointment with counselor_b that can be cancelled. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_05 | STG-S-0105 | Upcoming online session (E-Counseling consent) | UAT-ready (assignable) | STU-EC-01 | Yes — state changes | Upcoming ONLINE Appointment with counselor_a; no consent requested yet. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_06 | STG-S-0106 | Upcoming online session (E-Counseling consent) | UAT-ready (assignable) | STU-EC-02 | Yes — state changes | Upcoming ONLINE Appointment with counselor_b; no consent requested yet. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_07 | STG-S-0107 | Individual Inventory nearly complete | UAT-ready (assignable) | STU-INV-01 | Yes — state changes | Current Inventory saved as a nearly complete draft, ready to finish and submit. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_08 | STG-S-0108 | No Individual Inventory yet | UAT-ready (assignable) | STU-INV-02 | Yes — state changes | No current Inventory: starts one; Counseling booking requires it first. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_09 | STG-S-0109 | Routine Interview intake to prepare | UAT-ready (assignable) | STU-RI-01 | Yes — state changes | Upcoming Appointment with counselor_a and a Routine Interview intake draft. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_10 | STG-S-0110 | Graduating: Exit Interview open | UAT-ready (assignable) | STU-EXIT-01 | Yes — state changes | Graduating; Exit Interview opportunity opened by Head Guidance, not started. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_11 | STG-S-0111 | Graduating: Exit Interview open | UAT-ready (assignable) | STU-EXIT-02 | Yes — state changes | Graduating; Exit Interview opportunity opened by Head Guidance, not started. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_12 | STG-S-0112 | Eligible to request a Good Moral certificate | UAT-ready (assignable) | STU-GM-01 STU-MSG-02 | Yes — state changes | Submitted Inventory and no Good Moral request: requests a current-Student certificate. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_13 | STG-S-0113 | Graduate: Graduate Tracer not started | UAT-ready (assignable) | STU-GT-01 | Yes — state changes | Graduated June 2026 with Exit Interview; Graduate Tracer not started. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_14 | STG-S-0114 | Unread Guidance Message | UAT-ready (assignable) | STU-MSG-01 | Yes — state changes | counselor_a started the Appointment conversation; the Student has not read it. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_15 | STG-S-0115 | Published Shared Summary to read | UAT-ready (assignable) | STU-SUM-01 | Yes — state changes | Completed session with counselor_b; published Shared Summary and feedback invitation. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_16 | STG-S-0116 | Call Slip issued | UAT-ready (assignable) | STU-CS-01 | No — read-only | Referral and a Call Slip issued live by counselor_c for an interview this week. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_17 | STG-S-0117 | Good Moral request awaiting processing | UAT-ready (assignable) | STU-GM-05 | No — read-only | Good Moral request REQUESTED: counselor_b records the receipt, prepares and issues. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_18 | STG-S-0118 | Good Moral request ready for issuance | UAT-ready (assignable) | STU-GM-06 | No — read-only | Good Moral request READY_FOR_ISSUANCE: counselor_a issues and prints it. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_19 | STG-S-0119 | New referral awaiting a Call Slip | UAT-ready (assignable) | STU-CS-02 | No — read-only | Referral recorded by gss_a; no action yet: issue a Call Slip from it. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_20 | STG-S-0120 | New referral awaiting a Call Slip | UAT-ready (assignable) | STU-CS-03 | No — read-only | Referral recorded by counselor_b; no action yet: gss_b issues a Call Slip. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_21 | STG-S-0121 | Routine Interview evaluation pending | UAT-ready (assignable) | STU-RI-03 | No — read-only | Walk-in Encounter with a submitted intake: counselor_a finalizes the evaluation. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_22 | STG-S-0122 | Past Appointment awaiting an outcome | UAT-ready (assignable) | STU-FB-01 | Yes — state changes | A past Appointment with counselor_b still SCHEDULED: complete it or mark no-show. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_23 | STG-S-0123 | Past Appointment awaiting an outcome | UAT-ready (assignable) | STU-APT-06 | No — read-only | A past Appointment with counselor_c still SCHEDULED: complete it or mark no-show. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_24 | STG-S-0124 | Graduating: Exit Interview submitted | UAT-ready (assignable) | STU-GM-02 | Yes — state changes | Exit Interview submitted: Head Guidance may reopen it; Good Moral can be requested. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_25 | STG-S-0125 | Graduate: Graduate Tracer draft to complete | UAT-ready (assignable) | STU-GT-03 | Yes — state changes | Graduated June 2026 with historical Inventory and Exit Interview; Tracer draft. | Single-use action: once performed, a rerun does not restore the initial state. |
| ar_26 | STG-S-0126 | Graduate: ready to request Good Moral | UAT-ready (assignable) | STU-GM-07 | Yes — state changes | Graduated June 2026 with submitted Exit Interview and Tracer; no Good Moral request. | Single-use action: once performed, a rerun does not restore the initial state. |
| bg_65 | STG-S-0265 | Disabled Student account | Restricted (negative tests only) | NEG-02 | No — read-only | Disabled Student account (duplicate record closed by an administrator). | Disabled: cannot sign in. |

Background-only (64): `bg_01`, `bg_02`, `bg_03`, `bg_04`, `bg_05`, `bg_06`, `bg_07`, `bg_08`, `bg_09`, `bg_10`, `bg_11`, `bg_12`, `bg_13`, `bg_14`, `bg_15`, `bg_16`, `bg_17`, `bg_18`, `bg_19`, `bg_20`, `bg_21`, `bg_22`, `bg_23`, `bg_24`, `bg_25`, `bg_26`, `bg_27`, `bg_28`, `bg_29`, `bg_30`, `bg_31`, `bg_32`, `bg_33`, `bg_34`, `bg_35`, `bg_36`, `bg_37`, `bg_38`, `bg_39`, `bg_40`, `bg_41`, `bg_42`, `bg_43`, `bg_44`, `bg_45`, `bg_46`, `bg_47`, `bg_48`, `bg_49`, `bg_50`, `bg_51`, `bg_52`, `bg_53`, `bg_54`, `bg_55`, `bg_56`, `bg_57`, `bg_58`, `bg_59`, `bg_60`, `bg_61`, `bg_62`, `bg_63`, `bg_64`. They appear in rosters, filters and reports and are the targets named by some staff scenarios; do not assign them to evaluators.

## Guidance Counselor

Three Counselors own separate caseloads (Main CCMS/CAS/COENG, Main CBPA + Abaño COED, satellite campuses). Assign one evaluator per Counselor account; their Work Queues and rosters do not overlap except for office-wide Good Moral work.

| Account | ID | Why recommended | Assignable | Scenarios | Initial state changes? | What it starts with | Conflicts / limitations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| counselor_a | STG-E-0004 | Guidance Counselor (Main: CCMS, CAS, COENG) | UAT-ready (assignable) | CNS-APT-01 CNS-ENC-01 CNS-RI-01 CNS-REF-01 CNS-INV-01 CNS-GM-02 CNS-EC-01 CNS-WQ-01 CNS-MSG-01 CNS-REP-01 PND-FUP-01 | Yes — state changes | Counselor for the Main Campus CCMS, CAS and COENG caseload; supervises gss_a. | Sees only Students in CCMS, CAS and COENG. |
| counselor_b | STG-E-0005 | Guidance Counselor (Main CBPA, Abaño COED) | UAT-ready (assignable) | CNS-APT-02 CNS-RI-02 CNS-INV-02 CNS-GM-01 CNS-GM-03 CNS-ACT-01 | Yes — state changes | Counselor for the CBPA and COED caseload; supervises gss_b. | Sees only Students in CBPA and COED. |
| counselor_c | STG-E-0006 | Guidance Counselor (satellite campuses) | UAT-ready (assignable) | CNS-APT-03 CNS-REF-02 CNS-GM-04 CNS-AVL-01 NEG-06 | Yes — state changes | Counselor for Mercedes (CFAST), Labo (CANR), Jose Panganiban (COTT) and Entienza campuses. | Sees only satellite-campus Students; has no supervised staff. |
| unassigned_counselor | STG-E-0012 | Guidance Counselor without College responsibility | Restricted (negative tests only) | NEG-04 | No — read-only | A Counselor with no College responsibility: an empty assigned caseload. | Negative-scope testing only: sees no Student records. |

## Guidance Services Staff

Each staff account is supervised by one Counselor and works within that caseload. Assign gss_a with counselor_a's evaluator team and gss_b with counselor_b's.

| Account | ID | Why recommended | Assignable | Scenarios | Initial state changes? | What it starts with | Conflicts / limitations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gss_a | STG-E-0007 | Guidance Services Staff (supervised by counselor_a) | UAT-ready (assignable) | GSS-REF-02 GSS-GM-01 GSS-WQ-01 GSS-NEG-01 | Yes — state changes | Operational assistance within counselor_a's caseload: referrals, Call Slips, queue. | No counseling, Routine Interview or Shared Summary content. |
| gss_b | STG-E-0008 | Guidance Services Staff (supervised by counselor_b) | UAT-ready (assignable) | GSS-REF-01 GSS-EXIT-01 | Yes — state changes | Operational assistance within counselor_b's caseload: referrals, Call Slips, queue. | No counseling, Routine Interview or Shared Summary content. |
| former_staff | STG-E-0011 | Former Guidance Services Staff (disabled) | Restricted (negative tests only) | NEG-01 | No — read-only | Departed staff member; authored last year's referral and Call Slip. | Disabled: cannot sign in. Used to prove disabled accounts are refused. |

## Head Guidance Counselor

One Head account exists, as at the institution. If two evaluators share it, schedule their mutating scenarios (opportunities, reopen, reassignment) one at a time.

| Account | ID | Why recommended | Assignable | Scenarios | Initial state changes? | What it starts with | Conflicts / limitations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| head_guidance | STG-E-0003 | Head Guidance Counselor | UAT-ready (assignable) | HGC-SUP-01 HGC-ASN-01 HGC-EXIT-01 HGC-EXIT-02 HGC-REP-01 HGC-FB-01 HGC-AY-01 | Yes — state changes | Institution-wide supervision, Academic Years, Exit Interview opportunities and corrections, Services, reports and feedback results; has a consultation schedule. | One Head account exists; evaluators sharing it see each other's changes. |

## IT Administrator

Three equivalent accounts let three ITSO evaluators work independently. Use newly created synthetic accounts for account-management changes; never edit dataset accounts.

| Account | ID | Why recommended | Assignable | Scenarios | Initial state changes? | What it starts with | Conflicts / limitations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| it_admin | STG-E-0001 | IT Administrator | UAT-ready (assignable) | ITA-ACC-01 ITA-ORG-01 ITA-PLT-01 | Yes — state changes | Primary IT Administrator: accounts, access policy, organization, Platform Operations. | No access to confidential guidance records. |
| it_admin_2 | STG-E-0002 | IT Administrator (second evaluator) | UAT-ready (assignable) | ITA-POL-01 ITA-NEG-01 | Yes — state changes | Second IT Administrator for a parallel evaluator; same authority as it_admin. | No access to confidential guidance records. |
| it_admin_3 | STG-E-0014 | IT Administrator (third evaluator) | UAT-ready (assignable) | ITA-PLT-02 | No — read-only | Third IT Administrator for independent ITSO UAT; reviews platform health and access. | No access to confidential guidance records; do not modify dataset accounts. |

## Data Protection Officer

Two DPO accounts share one Privacy Notice catalog. Publishing a revision prompts every signed-in user, so schedule DPO-NOT-01 with the UAT lead.

| Account | ID | Why recommended | Assignable | Scenarios | Initial state changes? | What it starts with | Conflicts / limitations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dpo | STG-E-0009 | Data Protection Officer | UAT-ready (assignable) | DPO-RET-01 DPO-NOT-01 DPO-NEG-02 | Yes — state changes | Privacy Notices, privacy activity export and read-only retention oversight. | No confidential guidance content; no disposition operations exist. |
| dpo_2 | STG-E-0010 | Data Protection Officer (second evaluator) | UAT-ready (assignable) | DPO-ACT-01 DPO-NEG-01 | No — read-only | Second DPO account so two privacy evaluators do not share one identity. | Shares the same Privacy Notice catalog as dpo. |

## Institutional Officer

The undesignated officer exists only to prove refusals; issue its credential explicitly.

| Account | ID | Why recommended | Assignable | Scenarios | Initial state changes? | What it starts with | Conflicts / limitations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| officer_no_designation | STG-E-0013 | Institutional Officer without DPO designation | Restricted (negative tests only) | NEG-03 | No — read-only | An Institutional Officer with no designation: no effective capabilities. | Negative-authorization testing only: every protected workspace is refused. |

## Known shared-state conflicts

- `ar_24`: STU-GM-02 (request Good Moral) and HGC-EXIT-01 (reopen the Exit Interview) start from the same submitted interview; run the Head scenario last.
- `ar_05`: CNS-EC-01 (Counselor requests consent) must precede STU-EC-01 (Student decides); assign both to the same scheduled pair of evaluators.
- `head_guidance`, `dpo`/`dpo_2`: shared catalogs; serialize mutating scenarios.
- Changing Counselor responsibilities, Availability or the current Academic Year affects most scenarios; keep those out of UAT or run them last.
