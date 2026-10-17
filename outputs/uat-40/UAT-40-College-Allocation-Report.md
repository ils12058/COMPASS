# UAT-40 — College allocation correction and participant handoff

2026-10-17, Asia/Manila. Branch `feat/uat-40-college-allocation`; base `staging` @ `b917e0c8`
(also the deployed backend build). No migration, deployment, reset, seed, credential issuance or
live database write was performed.

## What was wrong

The 25 current-Student slots in `UAT_40_ALLOCATION` were all Main Campus action-ready or rich
accounts: CCMS 6, CAS 5, CBPA 5, COENG 2, COED 3, CFAST 1, CANR 2, COTT 0, Entienza 1.

## Correction

| College / unit | Target | Allocated accounts |
| --- | ---: | --- |
| CCMS | 3 | `ar_01`, `ar_05`, `ar_14` |
| CAS | 3 | `ar_03`, `ar_09`, `ar_12` |
| CBPA | 3 | `ar_02`, `ar_10`, `ar_22` |
| COENG | 3 | `ar_07`, `ar_19`, **`bg_47`** |
| COED | 3 | `ar_04`, `ar_15`, `ar_20` |
| CFAST | 3 | `ar_23`, **`bg_54`**, **`bg_55`** |
| CANR | 3 | `ar_08`, `ar_16`, **`bg_56`** |
| COTT | 2 | **`bg_58`**, **`bg_59`** |
| Entienza | 2 | `ar_24`, **`bg_60`** |

All seven candidate background accounts were eligible: CURRENT, affiliated with the College shown,
active, email verified, credential plan, submitted 2026-2027 Inventory. They are promoted to
UAT-ready (`PROMOTED_BACKGROUND`). Promotion changes only suitability and catalog text, which
seeding never reads; identity, affiliation, enrollment, Inventory and records are unchanged (the
identity fingerprint of all 116 accounts is frozen in the tests). Their scenarios start from records
the live dataset already has:

| Account | Scenario(s) | Starting state used |
| --- | --- | --- |
| `bg_47` | STU-APT-07 book Counseling (counselor_a) | No Appointment, submitted Inventory |
| `bg_54` | STU-GM-08 follow the assisted request from CNS-GM-04; STU-MSG-03 Office conversation | No Good Moral request, no Office thread |
| `bg_55` | STU-FB-02 feedback after a completed session | Completed session, open feedback invitation |
| `bg_56` | STU-APT-08 book Counseling (counselor_c) | No Appointment, submitted Inventory |
| `bg_58` | STU-GM-09 request a current-Student certificate | No Good Moral request |
| `bg_59` | STU-APT-09 reschedule an upcoming Appointment (counselor_c) | Upcoming in-person Appointment |
| `bg_60` | STU-APT-10 book Counseling (counselor_c) | No Appointment, submitted Inventory |

Seven Main Campus Students leave the 40 and stay UAT-ready reserves with their scenarios intact:
`first_year`, `second_year` (multi-domain history; STU-RI-02 duplicates STU-RI-01), `ar_06`
(second consent scenario), `ar_11` (second Exit Interview), `ar_17`, `ar_18`, `ar_21` (read-only
follow-ups of staff scenarios that still run). No existing scenario definition changed (all 94
pre-existing definitions keep their fingerprint). Totals: **116 accounts, 102 scenarios
(99 executable, 3 pending)**.

The manifest now refuses an allocation that disagrees with `UAT_40_STAKEHOLDER_COUNTS` or
`UAT_40_STUDENT_QUOTA`, or that puts a non-current, unaffiliated or wrong-College Student in a
current-Student slot. `verify` gained one read-only predicate (`feedback:invitation_pending`).
`report` writes a seventh document, `COMPASS-UAT-40-ASSIGNMENTS.csv`, and the Selection Guide now
shows the College table, the reserves and the exact 40 `--account` arguments.

## Final 40 accounts

| Stakeholder | Accounts |
| --- | --- |
| Head Guidance Counselor (1) | `head_guidance` |
| Guidance Counselors (3) | `counselor_a` (CCMS, CAS, COENG), `counselor_b` (CBPA, COED), `counselor_c` (CFAST, CANR, COTT, Entienza) |
| Guidance Services Staff (2) | `gss_a` (with counselor_a), `gss_b` (with counselor_b) |
| Current Students (25) | by College, table above |
| Alumni (5, GRADUATED) | `recent_graduate` (CAS), `alumni` (COED), `ar_13` (CBPA), `ar_25` (CCMS), `ar_26` (CBPA) |
| ITSO Personnel (3, IT_ADMIN) | `it_admin`, `it_admin_2`, `it_admin_3` |
| Data Protection Officer (1) | `dpo` |

## Validation

- `tests/test_staging_seed.py`: **47 passed**. New checks: exact stakeholder counts and College
  quota, College affiliation, lifecycle and credential plan of every slot, five distinct GRADUATED
  Alumni, staff roles and designations, one owner per scenario, no promoted state consumed twice,
  identity/scenario preservation fingerprints, each promoted Student completing its own scenario
  through domain services, the 40-row CSV, and issuance of **exactly 40 distinct credentials** in
  a disposable database (every other account kept no usable password; a rerun skips all 40).
- The remaining 16 files CI selects for this change (safety + staging-seed bundles): **356 passed**.
- Ruff lint and format, `git diff --check` and the backend CI selector self-tests passed.

## Live dataset preservation (rehearsal)

A disposable database was seeded with the deployed code (`b917e0c8`), reproducing the live
116-account dataset. With the corrected code against it: strict `verify` **PASSED** with zero
warnings (122 scenario checks), `report` wrote all seven documents, and a `pg_dump --data-only` was
byte-identical before and after. A `seed` rerun created **0 items** and also left the data
identical. **No live database write is required** to apply the corrected allocation.

## Authorized read-only live run

The owner authorized temporary SSH access from the operator's exact /32 and a read-only
verify/report with the corrected seeder (no seed, no credentials). One session, 09:31 Asia/Manila:

- Temporary firewall rule `136.158.101.147/32` added, then removed. The firewall was restored
  exactly; only the pre-existing SSH rule remains.
- The host deployment lock (`/opt/compass/.live-reset.lock`) was held throughout. No freeze file.
- Public `/api/v1/meta` and the running image both reported `b917e0c8`, live-staging.
- Compatibility: the uploaded seeder (`c7e1fb9f`, SHA-256-checked archive) had the same 37 files as
  the image's `/app/compass/staging_seed`. Only `manifest.py`, `reports.py`, `students.py` and
  `verify.py` differ; the running manifest was the 116-account, 94-scenario one.
- One-off `--rm --no-deps --pull never` containers on the existing image, with the corrected
  `staging_seed` mounted read-only over the image's copy. Application containers were untouched.
- Strict `verify`: **PASSED, zero warnings** (122 scenario checks). `report` wrote all seven documents.
- A read-only fingerprint of **93 models / 3,652 rows** was identical before and after. Migrations
  were unchanged (41), and there were 116 accounts with **0 usable passwords** both times.
- Container IDs, start times, images, volumes and network were unchanged. No one-off container
  was left.

**No live database write was required or made.** The seven live reports replace the repository
copies under `outputs/canon-1c/uat`. Every downloaded file matched its remote SHA-256. They are
byte-identical to the rehearsal set apart from the generated-at/database header line, and the two
CSVs are identical. Live copies stay at
`/opt/compass/operator/uat40-college-c7e1fb9f9d26354ac39db50938f7eaaf529c76e1-20261017T013139Z/reports`
(mode 0700), with the fingerprints and verification output beside them.

## Handoff documents

Generated into `outputs/uat-40/handoff/`, which is git-ignored so completed copies cannot be
committed. None contains a password, MFA secret, recovery code or token.

- `COMPASS-UAT-40-ACCOUNT-DISTRIBUTION-REGISTER.xlsx`: Register (40 rows; grey prefilled, yellow
  editable, dropdowns, date validation), Summary (formula progress by stakeholder and College),
  Scenarios (78 assigned scenarios), Instructions, Lists.
- `COMPASS-UAT-40-ACCOUNT-ASSIGNMENT-FORM.docx`: printable landscape form with the allocation,
  handoff rules, acknowledgement statement, 40 grouped rows and sign-off.
- `COMPASS-UAT-PARTICIPANT-INSTRUCTIONS.docx`: participant guide.
- `COMPASS-UAT-40-ASSIGNMENTS.csv`: the generated 40-row template.
- `tools/`: the scripts that rebuild the documents from the generated CSV.

## Credential issuance readiness (not executed)

1. Live read-only `verify` with the corrected code passes. Done 2026-10-17 (see above).
2. Owner authorizes issuance for exactly the 40 keys in the Selection Guide.
3. The deployed build already accepts all 40 keys: explicit `--account` selection needs only the
   CREDENTIAL plan, which every allocated account has. No deployment is required for issuance.
4. The prepared host script `/opt/compass/operator/live-reset/issue-selected-participant-credentials.sh`
   pins build `d86ddc08` and probes `/api/v1/meta` with the default Python client (which received
   HTTP 403 from the Droplet). Update both, or run the documented one-off compose command, before use.
5. Use a new 0700 handoff directory outside the repository with no existing handoff file.
6. Expect `Issued 40 credential(s); skipped 0`. Never run issuance without `--account`.
7. Deliver each password privately and separately from the assignment documents, record only the
   handoff in the register, then delete the handoff file.
8. Confirm the staff MFA plan (`AUTH_MFA_REQUIRED_ROLE_CODES`, step-up) and the support contact
   before the first sign-in.
9. Afterwards run `verify --allow-uat-changes`; exactly 40 accounts should hold a usable password.
