# Risks — SAR-1 and the proposed SAR consolidation

**Audit base:** `7afd442eed38d38ec2f18a7dc9c1715b412f5122`.
Likelihood/impact are audit judgments (**Inferred**) unless the mechanism is **Verified**.
No risk is accepted by this audit; owners must disposition them.

## 1. Risk register

| ID | Risk | Likelihood | Impact | Affected | Mitigation | Owner | Blocks SAR-1? |
|---|---|---|---|---|---|---|---|
| R1 | Backfilled affiliation is presented as verified academic placement | High if not controlled | High | Students, Registrar, GCO, reports | Default `UNVERIFIED`; no `.verify` grant; explicit UI/API labeling; reconciliation | Registrar + GCO | Yes |
| R2 | Profile Program and College disagree, creating a second split truth | High if Program is backfilled | High | Routing, Good Moral, counseling, reports | SAR-1 College-only; Program null; conflict rule D-SAR-19 before cutover | GCO + Registrar | Yes |
| R3 | Transfer/removal destroys the only placement record | **Verified** mechanism | High | Historical reporting, authorization history, Students | Do not delete profile on removal; preserve audit; decide D-SAR-07; backups | Registrar + Records | Yes |
| R4 | Dual-write diverges or creates a second writer | Medium | High | All affiliation consumers | Same transaction; single writer; reconciliation R1–R3; activation gate | IT | Yes |
| R5 | Stale lifecycle is mistaken for enrollment/current status | **Verified** mechanism | Medium | Eligibility, reports, operational lists | Keep lifecycle distinct; never derive enrollment; DQ-10; D-SAR-10 | Registrar + GCO | No (but affects data quality) |
| R6 | Program retirement leaves Students with an inactive Program | Medium | Medium | Inventory, Good Moral F4, reports | ORG D9/D12 remediation; do not rewrite history; surface in reconciliation | UCN + Registrar + GCO | No |
| R7 | SAR invents a term calendar or enrollment state | High if modeling starts before decisions | High | Period records, reports, audit | D-SAR-09/D-SAR-10 before any period table; no inferred defaults beyond `UNKNOWN` | Registrar + UCN | Yes for periods |
| R8 | Self-reported Tracer data becomes an official graduation record | High if backfilled | High | Graduates, certificates, reports | No graduation backfill; separate authority D-SAR-11; label source | Registrar + Records | Yes for graduation |
| R9 | Academic profile is exposed beyond intended scope | Medium | High | Students, privacy, GCO | No new grants in shadow phase; D-SAR-05/06; least privilege; audit access | IT + DPO + GCO | Yes if read endpoints added |
| R10 | Report coverage/profile denominators drift | **Verified** split-source mechanism | Medium | Reports, management decisions | No consumer cutover in SAR-1; D-SAR-20 reconciliation definitions before cutover | Records + IT | No for SAR-1; yes for cutover |
| R11 | FUP-3C proceeds against an unfinished SAR and changes follow-up visibility | Medium | High | Follow-ups, Students | Keep current affiliation scope; explicit dependency on SAR cutover gates | GCO + IT | No (external program risk) |
| R12 | Faculty academic-contact attestation is implemented without approval | Low if governance holds | High | Faculty, Students, privacy | FAC-D9 remains pending; no field or claim; D-SAR-18 | GCO + UCN + Registrar + DPO | No |
| R13 | Backfill locks tables or times out | Medium | Medium | Operations | Batched short transactions; off-peak window; dry-run counts; approved window | IT | Yes |
| R14 | Rollback after activation loses new writes | Medium | High | Students, operations | Gate off first; do not drop table; backup/restore rehearsal; point-of-no-return gate | IT | Yes |
| R15 | Audit metadata is insufficient to reconstruct prior placement | **Verified** limitation | Medium | History, disputes, reporting | Backups; retain audit; do not promise as-of reconstruction; period model later | Records + IT | No |
| R16 | Proposed profile cannot prove who verified what | **Verified** model gap | Medium | Verification claims, audit | Add verifier fields or define audit-only; D-SAR-02 | Registrar + IT | Yes |
| R17 | Consumer migration is underestimated (10+ domains) | **Verified** breadth | High | Delivery, routing, privacy | No consumer cutover in SAR-1; adapter-first plan; regression tests per domain | IT + GCO | No for SAR-1; yes for cutover |
| R18 | Academic records have no adopted retention category | **Verified** gap | High | Privacy compliance, storage | DPO/Records decision before new record activation; interim classification in D-SAR-06 | DPO + Records | Yes |
| R19 | Seeds/tests assume alignment that production does not enforce | **Verified** seed behavior | Medium | Test confidence, data quality | Add mismatch fixtures and aggregate checks; do not treat seed success as production proof | IT | No |
| R20 | Generated API/frontend contracts drift during migration | Medium | Medium | Frontend, clients | Keep affiliation contracts stable in SAR-1; additive-only endpoints; contract tests | IT | No |

## 2. Highest-priority risks — detail

### R1 — False verification

**Verified.** The proposal explicitly says migrated affiliations must not be classified as
Registrar-verified (lines 659–672). **Inferred.** A default value of `VERIFIED`, a UI label such as
“confirmed,” or a report that omits provenance would defeat that instruction. Mitigation: default
`UNVERIFIED`; no verification capability in SAR-1; display provenance wherever the profile is
shown; audit any later verification with actor and evidence.

### R2 — Split truth

**Verified.** Inventory submission does not compare the Program's College to the affiliation
(`be/compass/inventory/services.py:544-571`). **Verified.** Counseling context combines affiliation
College with Inventory Program (`be/compass/counseling/context_services.py:180-243`).
**Verified.** Reports use affiliation for current-year coverage and Inventory for profiling
(`be/compass/reports/services.py:413-433,1011-1027`). Any SAR model that copies both without a
precedence rule reproduces the conflict. Mitigation: College-only SAR-1; D-SAR-19 before cutover;
reconciliation query DQ-04.

### R3 — Destructive history

**Verified.** Transfer updates in place; removal deletes (`be/compass/organization/services.py:271-325`).
**Inferred.** A profile that mirrors removal by deletion would repeat the same defect at a second
layer. Mitigation: null/flag rather than delete; D-SAR-07; preserve audit; no history claim in
SAR-1.

### R4 — Dual-write divergence

**Verified.** The affiliation service is transactional and row-locked
(`be/compass/organization/services.py:271-303`). **Inferred.** A mirror outside that transaction, an async
task, or a second admin path would diverge under failure or concurrency. Mitigation: same
transaction; fail the affiliation write if the mirror fails; reconciliation; activation gate off by
default; no direct profile writes in UI.

### R9 — Scope and privacy

**Verified.** Today affiliation reads are gated by `organization.manage`, while operational domains
use affiliation for scoped access. **Verified.** No academic capability or Registrar role exists
(`be/compass/accounts/policy.py:20-76,608-760`). **Inferred.** Bolting `.view` onto an existing role
would silently broaden academic-data access. Mitigation: no grants in the shadow phase; explicit
scope decision D-SAR-05; DPO review D-SAR-06; audit every read if a staff projection is added.

## 3. Risk acceptance and review

- Each risk needs a named institutional owner and a disposition (`accept`, `mitigate`, `transfer`,
  `reject`) before SAR-1 implementation.
- R1, R2, R3, R4, R9, R14, R16 and R18 are SAR-1 gates; they cannot be accepted silently by the
  implementation team.
- R7, R8, R11, R12, R17 and R20 are later-phase gates; they do not block a College-only shadow
  profile but must be closed before the corresponding model or consumer moves.

## 4. Early-warning indicators

- Reconciliation R1/R2/R3 nonzero.
- Any profile row marked `VERIFIED` without an approved actor/evidence.
- Any affiliation write that succeeds while the profile write fails (should be impossible).
- Any report count change after a SAR-1 deployment that was supposed to be read-only.
- Any Student routing/appointment change that cannot be explained by an affiliation change.
- Any new code path that writes the profile outside the approved service.
- Any attempt to add academic fields to CSV import before D-SAR-15.
