# Staging Dataset v1 — Summary

COMPASS Staging Dataset v1 (dataset version 1). Generated 2026-10-16T22:02:57+08:00 by `seed_staging_dataset report` from the manifest and a passing read-only verification of the local-staging database. Do not edit by hand: change `be/compass/staging_seed/` and regenerate.

All names, identifiers, addresses and email addresses are synthetic. This document contains no passwords, MFA secrets, tokens, confidential form answers or counseling content, and no evaluator identities.

## Dataset

- Dataset: **COMPASS Staging Dataset v1**, dataset version **1** (independent of the COMPASS application and API versions; not an upgrade of Demo Dataset v1/v2).
- Timeline: Academic Years 2024-2025, 2025-2026 and current 2026-2027, Asia/Manila. Preparation dates supported: 2026-09-21 to 2027-04-30. Seed runs recorded on: 2026-10-16.
- Accounts: **113** (100 Students, 13 staff).
- Executable UAT scenarios: **88**; pending-implementation scenarios: **3**.
- Verification: **PASSED** — Schema readiness: 5 passed, 0 failed, 0 warnings; Canonical configuration: 57 passed, 0 failed, 0 warnings; Account readiness: 1085 passed, 0 failed, 0 warnings; Organization routing: 12 passed, 0 failed, 0 warnings; Scenario initial states: 101 passed, 0 failed, 0 warnings; Workflow integrity: 40 passed, 0 failed, 0 warnings; Privacy and security: 142 passed, 0 failed, 0 warnings; External side effects: 5 passed, 0 failed, 0 warnings.

## Accounts

### Students by group

| Value | Count |
| --- | --- |
| ACTION_READY | 24 |
| BACKGROUND | 65 |
| RICH_SCENARIO | 11 |

### Accounts by assignment suitability

| Value | Count |
| --- | --- |
| BACKGROUND | 64 |
| RESTRICTED | 4 |
| UAT_READY | 45 |

### UAT-ready accounts by role

| Value | Count |
| --- | --- |
| Data Protection Officer | 2 |
| Guidance Counselor | 3 |
| Guidance Services Staff | 2 |
| Head Guidance Counselor | 1 |
| IT Administrator | 2 |
| Student | 35 |

### Authentication state (from the database)

| Value | Count |
| --- | --- |
| Awaiting credential issuance | 110 |
| Disabled | 2 |
| Onboarding (never signed in) | 1 |

### Students by lifecycle

| Value | Count |
| --- | --- |
| CURRENT | 86 |
| FORMER | 4 |
| GRADUATED | 10 |

## Academic distribution

### Students by enrollment campus

| Value | Count |
| --- | --- |
| ABANO | 16 |
| ENTIENZA | 4 |
| LABO | 5 |
| MAIN | 69 |
| MERCEDES | 3 |
| PANGANIBAN | 3 |

### Students by College

| Value | Count |
| --- | --- |
| ABANO/COED | 16 |
| ENTIENZA/ENTIENZA | 4 |
| LABO/CANR | 5 |
| MAIN/CAS | 22 |
| MAIN/CBPA | 21 |
| MAIN/CCMS | 21 |
| MAIN/COENG | 5 |
| MERCEDES/CFAST | 3 |
| PANGANIBAN/COTT | 3 |

### Students by Program

| Value | Count |
| --- | --- |
| CANR/BSABE | 1 |
| CANR/BSAGRI | 3 |
| CANR/BSES | 1 |
| CAS/BAELS | 2 |
| CAS/BASOC | 1 |
| CAS/BSAM | 1 |
| CAS/BSBIOL | 8 |
| CAS/BSDEVCOM | 2 |
| CAS/BSPSYCH | 8 |
| CBPA/BPA | 1 |
| CBPA/BSA | 7 |
| CBPA/BSBA | 8 |
| CBPA/BSENTREP | 1 |
| CBPA/BSHM | 3 |
| CBPA/BSOA | 1 |
| CCMS/BSIS | 9 |
| CCMS/BSIT | 12 |
| CFAST/BSF | 3 |
| COED/BEED | 6 |
| COED/BPED | 1 |
| COED/BSED | 8 |
| COED/BTLED | 1 |
| COENG/BSCE | 2 |
| COENG/BSEE | 2 |
| COENG/BSME | 1 |
| COTT/BSINDTECH | 1 |
| COTT/BTVTED | 2 |
| ENTIENZA/BEED | 1 |
| ENTIENZA/BSED | 2 |
| ENTIENZA/BSENTREP | 1 |

### Current Students by year level

| Value | Count |
| --- | --- |
| 1 | 19 |
| 2 | 28 |
| 3 | 23 |
| 4 | 15 |
| 5 | 1 |

## Workflow states

### Current-year Individual Inventory

| Value | Count |
| --- | --- |
| draft | 10 |
| missing | 7 |
| submitted | 69 |

### Appointments

| Value | Count |
| --- | --- |
| CANCELLED | 3 |
| COMPLETED | 5 |
| NO_SHOW | 2 |
| SCHEDULED (past, awaiting outcome) | 2 |
| SCHEDULED (upcoming) | 13 |

### Appointment delivery modes

| Value | Count |
| --- | --- |
| IN_PERSON | 21 |
| ONLINE | 4 |

### Shared Summaries

| Value | Count |
| --- | --- |
| draft | 1 |
| published | 3 |

### Routine Interviews

| Value | Count |
| --- | --- |
| evaluation finalized | 3 |
| evaluation pending | 3 |
| intake draft | 2 |

### Referrals

| Value | Count |
| --- | --- |
| no action yet | 2 |
| voided | 1 |
| with action | 4 |

### Call Slips

| Value | Count |
| --- | --- |
| HISTORICAL completed | 2 |
| HISTORICAL voided | 1 |
| LIVE open | 2 |

### Good Moral requests

| Value | Count |
| --- | --- |
| CANCELLED | 1 |
| ISSUED | 2 |
| READY_FOR_ISSUANCE | 1 |
| REQUESTED | 3 |

### Exit Interviews

| Value | Count |
| --- | --- |
| 2024-2025 SUBMITTED | 1 |
| 2025-2026 SUBMITTED | 9 |
| 2026-2027 DRAFT | 3 |
| 2026-2027 SUBMITTED | 3 |

### Graduate Tracer

| Value | Count |
| --- | --- |
| DRAFT | 1 |
| SUBMITTED | 7 |

### Student notifications

| Value | Count |
| --- | --- |
| read | 3 |
| unread | 49 |

### Announcements

| Value | Count |
| --- | --- |
| ARCHIVED | 1 |
| DRAFT | 1 |
| PUBLISHED | 4 |

### Resources

| Value | Count |
| --- | --- |
| ARCHIVED | 1 |
| DRAFT | 1 |
| PUBLISHED | 4 |

### Other totals

| Record | Count |
| --- | --- |
| Inventories (all years) | 109 |
| Counseling Encounters | 10 |
| Referral actions | 4 |
| Open Exit Interview opportunities | 5 |
| Guidance Message threads | 1 |
| Customer Feedback responses | 6 |
| CSM responses | 6 |
| Colleges with a Counselor | 9 of 10 |

## Known limitations

- The population is a UAT design, not a statistical model of UCN enrollment.
- The Graduate School has no Counselor responsibility and no seeded Students.
- No Daily room, recording, transcript or provider session is created; joining an E-Counseling call needs an operator-approved provider plan.
- Structured PSGC geography stays 'not specified'; no Resource files are uploaded.
- Seeding creates in-app notifications only; live UAT actions send normal staging email to the dataset addresses.
- Appointment Reminders, Service Catalog Expansion and Shared Guidance Follow-Up Management are pending; their scenarios are not executable on this baseline.
