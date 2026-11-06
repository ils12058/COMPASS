# GMSG-0 — Validation record

Slice: **GMSG-0 — Guidance Messages Expansion architecture, privacy and permission audit**
(documentation only).
Audit base: `de6902200878f1413bea7a5a90166d30be92bdfc` · branch `integration/ux15-modernization` ·
performed 2026-11-06.

This file is the audit's honesty record: what was executed, what was read, what was **not** run, and
what the evidence therefore cannot prove.

---

## 1. Method

1. **Gate first.** Confirm HEAD, branch and working-tree state before reading anything, using only
   the four commands brief §6 allows (`git rev-parse HEAD`, `git rev-parse --abbrev-ref HEAD`,
   `git status --short`, `git diff --check`). No reset, checkout, stash, merge, rebase, commit or
   push at any point.
2. **Read the source of truth, not the summary.** Every claim in this package was resolved against
   the file at the cited line at this commit. Proposal text was read for *scope*, never used as
   evidence of behavior.
3. **Static inspection only** — `grep -n`, `sed -n`, `cat`, `awk`, `ls`, `wc`, `find` and the
   read/search tools. Nothing executed the application.
4. **Breadth delegated, depth verified.** Four read-only Explore/general-purpose agents surveyed the
   FE messaging surfaces, realtime + notifications + work queues, the FAC/referral/SAR dependencies
   and the CONT/CENC/FUP dependencies. Their file/line leads were then re-read directly before any
   claim was written down; where an agent's count or line range disagreed with the file, the file
   won (see §7).
5. **Self-audit pass.** After drafting, the package's own citations were re-resolved mechanically
   (link resolution, line-number ranges, count tables) and three of my own claims were corrected —
   recorded in §7 rather than silently edited.
6. **Claim labels.** **Verified** = read at the cited line at this commit. **Inferred** = a
   consequence of verified code, stated as a consequence. **Unknown** = not established; listed as
   open in `decisions.md`/`risks.md` instead of guessed.

---

## 2. Start-state gate result

| Check | Required | Actual | Result |
|---|---|---|---|
| HEAD | `de6902200878f1413bea7a5a90166d30be92bdfc` | identical | **Met** |
| Branch | `integration/ux15-modernization` | identical | **Met** |
| Tracked modifications | none | none (`git diff --check` exit 0, no output; `git status --short` listed no modified tracked file) | **Met** |
| Untracked entries | only `Claude outputs/`, `outputs/paper-screenshots/` | exactly those two, plus `docs/gmsg-0/` (created by this audit) | **Met** |
| Remote parity (incidental) | — | `origin/integration/ux15-modernization` == the required SHA | noted, not required |

The gate passed on the first check, so no stop condition was triggered at start.

---

## 3. Inspected scope

| Area | What was read |
|---|---|
| `be/compass/guidance_messages/` | All of `models.py` (227 lines), `policy.py` (165), `content.py`, `services.py` (501), `api.py` (682), `work.py`, `student_actions.py`, `errors.py`, the `rotate_guidance_message_encryption` command, migrations |
| `be/compass/accounts/` | `policy.py` role/capability/ceiling/grant tables, `models.py` (`has_capability`, `UserCapabilityOverride`) |
| `be/realtime_service/` | `protocol.py` (event registry, channels, validation, close codes), `app.py` (inbound frame policy, lifetime) |
| `be/compass/realtime/` | `publish.py` |
| `be/compass/notifications/` | `policy.py` (event + target enums, definitions), `email_links.py`, `current.py`, `api.py`, `delivery.py`, `push.py`, `push_policy.py` |
| Neighbouring domains | `counseling/continuity_models.py`, `continuity_access.py`, `continuity_services.py`, `student_session_summaries.py`; `referrals/models.py`, `faculty_services.py`, `faculty_api.py`, `administrative_state.py`, `provisional_activation.py`; `student_academics/models.py`, `reads.py`; `appointments/services.py`; `guidance_followups/models.py`, `policy.py`; `audit/actions.py` |
| Frontend | `fe/src/features/guidance-messages/**` (access, presentation, conversation surface, new-message, errors, data, freshness), `fe/src/lib/realtime/realtime-protocol.ts`, `fe/src/features/notifications/notification-targets.ts` |
| Contracts | `contracts/openapi.json` (presence/shape only — never opened for edit), generated client directory listing |
| Repo docs | `docs/cenc-0/**`, `docs/fup-0/**`, `docs/notif-04/**`, ADR files under `be/docs/decisions/`, `fe/AGENTS.md`, `be/AGENTS.md` |
| Proposal | `/Users/reynantlntno/Downloads/COMPASS Proposals/COMPASS Development Proposal Notes - Fifteen Proposals.md`, §18 family at lines **7959–9012** (§26 decision table at 8855–8878) |
| Tests | `be/tests/test_guidance_messages*.py` — **inventoried only, never executed** |

Not inspected: `node_modules`, build output, `.venv`, database dumps, any file outside the above.

---

## 4. Commands run, verbatim

All 37 shell invocations of the session, in order. Group A is the §6-allowed gate; Group B is the
static inspection §6 permits ("`rg`, `find`, `wc`, `git log`, `git show`" and equivalents — here
`grep -n`, `sed -n`, `cat`, `awk`, `ls`, `wc`, `find`, which are the same read-only character);
Group C is the post-draft self-audit of this package's own citations; Group D is the meta-inspection
that produced the count in this section. Failures are reproduced with their stderr.

### Group A — gate

```text
[1] cd /Users/reynantlntno/Projects/COMPASS && git rev-parse HEAD && git rev-parse --abbrev-ref HEAD && git status --short
[2] cd /Users/reynantlntno/Projects/COMPASS && git fetch origin && git rev-parse origin/integration/ux15-modernization
[18] git diff --check; echo "exit=$?"
[19] git rev-parse HEAD; git rev-parse --abbrev-ref HEAD; git status --short
```

`[1]` → HEAD `de6902200878f1413bea7a5a90166d30be92bdfc`, branch `integration/ux15-modernization`,
untracked `Claude outputs/`, `outputs/paper-screenshots/` (and, at `[19]`, `docs/gmsg-0/`).
`[18]` → `exit=0`, no output.
`[19]` → same SHA/branch as `[1]`: nothing drifted during the audit.

> **⚠ Out-of-scope command, disclosed.** `[2] git fetch origin` is **not** in brief §6's allowed
> list. It was run to confirm the required HEAD had actually landed on the integration branch rather
> than only locally. It performs no working-tree change and no history rewrite; its only effect is
> updating `.git/refs/remotes/origin/*` (and `ORIG_HEAD`-free FETCH_HEAD). It is reported here
> because the brief requires recording every command, and because an undisclosed network/git
> operation would make this record dishonest. Nothing was pushed, committed, tagged, checked out,
> reset, stashed, merged or rebased.

### Group B — static inspection of the codebase, docs and proposal

```text
[3] cd /Users/reynantlntno/Projects/COMPASS && grep -n "operation_id" be/compass/guidance_messages/api.py | wc -l && grep -n "operation_id" be/compass/guidance_messages/api.py
[4] cd /Users/reynantlntno/Projects/COMPASS && ls be/compass/guidance_messages/ && wc -l be/compass/guidance_messages/*.py && ls be/compass/management/commands/ 2>/dev/null | grep -i -E "guidance|message|key|rotate" ; find be -name "*.py" -path "*commands*" | xargs grep -ln "GUIDANCE_MESSAGE_ENCRYPTION_KEYS" 2>/dev/null
[5] cd /Users/reynantlntno/Projects/COMPASS && ls be/tests/ | grep -i guidance_messages && grep -c "^def test\|^    def test" be/tests/test_guidance_messages*.py && grep -rc "^def test_\|^    def test_" be/tests/test_guidance_messages*.py | awk -F: '{s+=$2} END {print "TOTAL:",s}'
[6] cd /Users/reynantlntno/Downloads/COMPASS Proposals && grep -n "^## 1[0-9]\.\|^### 18\." "COMPASS Development Proposal Notes - Fifteen Proposals.md" | awk -F: '$1>7950 && $1<9020'          # FAILED, see §5
[7] cd /Users/reynantlntno/Projects/COMPASS && ls docs/ | head -60 && echo "---CENC0---" && ls docs/cenc-0/ 2>/dev/null && echo "---FUP0---" && ls docs/fup-0/ 2>/dev/null
[8] grep -n "^## 1[0-9]\.\|^### 18\." "/Users/reynantlntno/Downloads/COMPASS Proposals/COMPASS Development Proposal Notes - Fifteen Proposals.md" | awk -F: '$1>7950 && $1<9020'                # retry of [6]
[9] grep -n "^## [1-9]\." "/Users/reynantlntno/Downloads/COMPASS Proposals/COMPASS Development Proposal Notes - Fifteen Proposals.md" | awk -F: '$1>7950 && $1<8300'
[10] grep -n "^## " "/Users/reynantlntno/Downloads/COMPASS Proposals/COMPASS Development Proposal Notes - Fifteen Proposals.md" | awk -F: '$1>7959 && $1<8960'
[11] cd /Users/reynantlntno/Projects/COMPASS && sed -n '140,290p' be/compass/guidance_messages/api.py && echo "=== StudentAffiliation ===" && grep -rn "class StudentAffiliation" be/ | head -3 && echo "=== ADRs ===" && ls be/docs/decisions/ | grep -iE "10[0-9]" | head -20
[12] cd /Users/reynantlntno/Projects/COMPASS && sed -n '40,56p' be/realtime_service/protocol.py && echo "=== student_actions ===" && cat be/compass/guidance_messages/student_actions.py && echo "=== fup-0 README head ===" && sed -n '1,40p' docs/fup-0/README.md
[13] cd /Users/reynantlntno/Projects/COMPASS && grep -n "guidance_messages\." be/compass/accounts/policy.py | head -30 && echo "=== override model ===" && grep -n "class .*Override\|class CapabilityGrant\|def has_capability" be/compass/accounts/models.py be/compass/accounts/policy.py | head -12
[14] cd /Users/reynantlntno/Projects/COMPASS && grep -n "^def \|^@router\|^ERRORS\|    \"/" be/compass/guidance_messages/api.py | sed -n '1,80p'
[15] cd /Users/reynantlntno/Projects/COMPASS && echo "caps:" && grep -c "code=\"" be/compass/accounts/policy.py && echo "capability entries:" && grep -c "        code=\"[a-z_]*\.[a-z_.]*\"" be/compass/accounts/policy.py && echo "roles:" && grep -cn "RoleDefinition(" be/compass/accounts/policy.py && echo "FE feature files:" && ls fe/src/features/guidance-messages/ | grep -v "^$" | wc -l && echo "guidance tests:" && ls be/tests/ | grep -c guidance_messages
[16] cd /Users/reynantlntno/Projects/COMPASS/fe/src && grep -n "Student\|Guidance Office\|Message" features/guidance-messages/guidance-messages-presentation.ts | sed -n '1,25p' && echo "=== surface ===" && grep -n "Student" features/guidance-messages/guidance-conversation-surface.tsx && echo "=== new ===" && grep -n "Student\|Guidance Office" features/guidance-messages/guidance-new-message.tsx | head -20 && echo "=== errors ===" && grep -n "\"" features/guidance-messages/guidance-messages-errors.ts | head -20
[17] cd /Users/reynantlntno/Projects/COMPASS && grep -rn "429" be/compass/common/*.py be/compass/guidance_messages/*.py be/config/*.py 2>/dev/null | head -10; grep -rn "throttl\|ratelimit\|RATE_LIMIT" be/ --include=*.py -i | grep -v test | head -10   # second half FAILED, see §5
[23] cd /Users/reynantlntno/Projects/COMPASS && sed -n '200,208p;329,336p' be/compass/guidance_messages/services.py | cat -n; echo "=== notif-04 matrix line 43 ==="; sed -n '41,45p' docs/notif-04/event-channel-matrix.md; echo "=== accounts policy 633-637 ==="; sed -n '633,637p' be/compass/accounts/policy.py; echo "=== accounts policy 725-729 ==="; sed -n '725,729p' be/compass/accounts/policy.py
[24] cd /Users/reynantlntno/Projects/COMPASS && echo "=== 655-662 ==="; sed -n '655,662p' be/compass/accounts/policy.py; echo "=== 700-706 ==="; sed -n '700,706p' be/compass/accounts/policy.py; echo "=== shared_summary grep in be ==="; grep -rn "shared_summary" be/ --include="*.py" | head -12; echo "=== shared_summaries.py exists? ==="; ls be/compass/counseling/ | head -30
[25] cd /Users/reynantlntno/Projects/COMPASS && echo "=== notifications/policy.py 22-72 ==="; sed -n '22,72p' be/compass/notifications/policy.py; echo "=== grep COUNSELING_SHARED_SUMMARY in be ==="; grep -rn "COUNSELING_SHARED_SUMMARY\|shared_summary.published" be/compass/ | head; echo "=== grep publish_assigned_shared_summary ==="; grep -rn "publish_assigned_shared_summary" be/ | head
[27] cd /Users/reynantlntno/Projects/COMPASS && grep -rn "STUDENT_SESSION_SUMMARY_PUBLISHED" be/compass/ --include="*.py" | head; echo "=== def publish in student_session_summaries ==="; grep -n "^def \|^    def " be/compass/counseling/student_session_summaries.py | head -20; echo "=== does shared_summaries.py exist? ==="; ls be/compass/counseling/shared_summaries.py be/compass/counseling/shared_summary_content.py 2>&1   # exit 1 = intended absence
[34] cd /Users/reynantlntno/Projects/COMPASS && awk 'NR>=630 && NR<=740 && (/^    "[A-Z_]+": frozenset/ || /^    "[A-Z_]*": FACULTY/ || /guidance_messages\./)' be/compass/accounts/policy.py | cat -n; echo "=== exact def lines ==="; grep -n '^    "[A-Z_]*": \(frozenset\|FACULTY\)' be/compass/accounts/policy.py; echo "=== 150-175 ==="; sed -n '150,175p' be/compass/accounts/policy.py
[35] cd /Users/reynantlntno/Projects/COMPASS && sed -n '756,800p' be/compass/accounts/policy.py
[36] cd /Users/reynantlntno/Projects/COMPASS && sed -n '76,92p' be/compass/accounts/policy.py; echo "=== ceiling guidance codes? ==="; awk 'NR>=79 && NR<=140' be/compass/accounts/policy.py | grep -c guidance_messages; echo "=== ts lines 1-8 ==="; sed -n '1,8p' fe/src/features/guidance-messages/guidance-messages-access.ts
```

Plus, in the same read-only character, **31 `Read` calls across 18 distinct files** (14 of them in
`be/compass/guidance_messages/`, 7 the proposal document itself) and **8 `Grep` tool calls**. The
`Read`/`Grep` calls are not reproduced here because they are addressed by path in the deliverables;
every one of their results either appears as a `path:line` citation or was discarded.

### Group C — self-audit of this package's citations

```text
[20] wc -l docs/gmsg-0/*.md 2>/dev/null; echo "---"; ls -la docs/gmsg-0/
[21] grep -o '](\.\.[^)]*)' docs/gmsg-0/README.md | sort -u | head -20; echo "=== current-state ==="; grep -o '](\.\.[^)]*)' docs/gmsg-0/current-state.md | sort -u | head -20; echo "=== counts by prefix ==="; for f in docs/gmsg-0/*.md; do echo "$f: rel=$(grep -c '](\.\.' $f) fileabs=$(grep -c '](file:///' $f) plain=$(grep -c '](be/\|](fe/\|](docs/\|](contracts/' $f)"; done
[22] grep -n "policy\.py" docs/gmsg-0/access-matrix.md | head -8; echo "=== source-lifecycle ==="; grep -n "continuity_models" docs/gmsg-0/source-lifecycle.md | head -5; echo "=== implementation-plan links ==="; grep -n '](\.\.' docs/gmsg-0/implementation-plan.md
[26] cd /Users/reynantlntno/Projects/COMPASS && grep -n "shared_summary\|notif-04" docs/gmsg-0/*.md
[32] cd /Users/reynantlntno/Projects/COMPASS && echo "=== remaining ../../../ ==="; grep -c '\.\./\.\./\.\./' docs/gmsg-0/*.md; echo "=== all markdown relative links ==="; grep -oh '](\.\.[^)]*' docs/gmsg-0/*.md | sed 's/](//' | sort -u | while read p; do case "$p" in *"#"*) pp="${p%%#*}";; *) pp="$p";; esac; rel=$(python3 -c "import os,sys;print(os.path.exists(os.path.join('docs/gmsg-0',sys.argv[1])))" "$pp"); echo "$rel  $p"; done | sort | uniq -c | sort -rn | head -30; echo "=== file:/// leftovers ==="; grep -c 'file:///absolute' docs/gmsg-0/*.md
[33] cd /Users/reynantlntno/Projects/COMPASS && grep -n "363\|L11-L14\|586" docs/gmsg-0/*.md; echo "=== api.py 586-600 ==="; sed -n '584,598p' be/compass/guidance_messages/api.py
```

`[32]` confirmed every relative link in the package resolves to an existing file (18 distinct
targets, all `True`). `[33]` established the citation convention used throughout: a block range
starts at its decorator line, so `services.py:363-376` is `@transaction.atomic` + `def mark_read`
through `return state`, and `api.py:586-596` is the `PATCH /threads/{id}/read` operation.

### Group D — producing this record

```text
[28] python3 - <<'PY'  … transcript scan: list every Bash command …  PY
[29] python3 - <<'PY'  … transcript scan: failed commands + Write/Edit/Agent targets …  PY
[30] grep -c "no matches found" /Users/reynantlntno/.qoder/projects/-Users-reynantlntno-Projects-COMPASS/41189233-9a15-45fa-8ef2-e0241b71a6b0.jsonl; python3 - <<'PY'  … results for the 429 / --include / git fetch commands …  PY
[31] python3 - <<'PY'  … transcript scan: every errored tool result …  PY
[37] cd /Users/reynantlntno/Projects/COMPASS && python3 - <<'PY'  … full verbatim command dump + Read/Grep/Agent counts …  PY
```

These read the **session transcript** (`.jsonl` under `~/.qoder/projects/…`), not the repository, in
order to enumerate the commands honestly rather than from memory. They touched no application file,
and the transcript contains only paths and this audit's own text — no credentials, no Student PII,
no message bodies. `[37]` is the only one of the five run from inside the repo directory; the other
four ran from the session's working directory with absolute paths.

---

## 5. First-run failures, verbatim

Two commands failed on first attempt. Both were shell-quoting mistakes in my own invocation, not
repository defects, and neither produced a partial write.

**Failure 1 — `[6]`, unquoted path containing a space**

```text
$ cd /Users/reynantlntno/Downloads/COMPASS Proposals && grep -n "^## 1[0-9]\.\|^### 18\." "COMPASS Development Proposal Notes - Fifteen Proposals.md" | awk -F: '$1>7950 && $1<9020'
Exit code 1
(eval):cd:1: string not in pwd: /Users/reynantlntno/Downloads/COMPASS
```

Cause: `cd A B` passes `B` as a second argument; zsh rejected it. Fix: **`[8]`** quoted the full
absolute path and dropped `cd`. Retried once, succeeded, and `[9]`/`[10]` refined the section map
with it.

**Failure 2 — `[17]`, unquoted `--include` glob**

```text
$ grep -rn "throttl\|ratelimit\|RATE_LIMIT" be/ --include=*.py -i | grep -v test | head -10
(eval):1: no matches found: --include=*.py
```

Cause: zsh expanded `*.py` before `grep` saw it. The first half of `[17]` (the `429` search over
`common/`, `guidance_messages/`, `config/`) did run and returned nothing for `guidance_messages`.
Fix: re-issued as the `Grep` tool with `glob: "*.py"`. Outcome recorded where it belongs —
**rate limiting exists only in the Faculty referral path** (`referrals/faculty_services.py:180-198`,
`referrals/faculty_api.py:110`, `settings.py:188-192`) and **not** in Guidance Messages
(`api.py:285`: `ERRORS = (401, 403, 404, 409, 422, 503)`) — which is risk **R-10**.

**Non-failure that exits non-zero — `[27]`.** The trailing
`ls be/compass/counseling/shared_summaries.py be/compass/counseling/shared_summary_content.py`
returned exit 1 *because those modules do not exist as source*. That absence was the point of the
command and became the corrected R-21 finding. Only `.pyc` remnants exist under
`be/compass/counseling/__pycache__/`, which `ls` of the source tree correctly does not show.

---

## 6. Deliberately not run

Brief §6 names these. None was run, and no conclusion in this package depends on running them.

| Not run | Reason |
|---|---|
| `pytest` / any test, including `be/tests/test_guidance_messages*.py` | GMSG-0 runs **no application tests**. Tests were inventoried by static count only (`current-state.md` §11). A documentation audit cannot make a test claim; executing them would also require a database (§6) |
| `python manage.py check` / `makemigrations` / `migrate` / any Django management command | Django checks require settings + DB connectivity; `makemigrations` writes files; `migrate` mutates state. The rotation command was read, never invoked — not even with `--dry-run`, because "no management commands that write" is the rule and its dry-run behavior was only assumed |
| Any database access, query, shell, or data mutation | §2.2 forbids it. Every behavioral claim about constraints, partial indexes, `CheckConstraint`s, locking and idempotency is therefore **static** — the register states the DDL that exists, not its observed effect |
| OpenAPI schema generation and the contract check | §2.3 forbids generated/contract edits; regeneration would rewrite `contracts/openapi.json`. The DTO shape was read from `api.py:49-63` instead |
| FE unit/component test suites, `tsc` typecheck, ESLint, `next build` | No FE change was made. Copy/behavior claims cite source lines, not render output |
| Browser / Playwright suites, dev server | No UI was exercised. `ux-journeys.md` describes shipped code paths and quotes shipped strings; it makes **no** claim about visual result, focus order or screen-reader output beyond what the JSX attributes state |
| Deployment, containers, infra, seeding, fixtures | Out of scope and unauthorized; nothing in COMPASS was deployed for this audit |
| `git log` / `git show` beyond commit identification | The brief permits them for history; only the HEAD/branch/remote-parity reads in `[1]`/`[2]` and the CENC-4 provenance were needed. Prior-slice claims were verified against **current files**, not against commit messages, because §2.9 makes proposal/history text non-evidence |

**What was run instead:** the four §6-allowed gate commands, static inspection (§4 Groups A–D), one
out-of-scope `git fetch` (disclosed in §4 Group A), and read/grep/search tool calls.

---

## 7. Evidence limits

Static inspection can establish what the code *says*. It cannot establish the following, and this
package does not claim them:

1. **Runtime enforcement.** `CheckConstraint`s, the partial unique indexes
   (`models.py:110-114`, `GuidanceMessage` uniqueness at `:134-142`) and `PROTECT` behavior were read
   as DDL. Their real behavior under concurrent writers is **Unknown** here. R-11 (lock-order
   deadlock) and R-17 (read-cursor monotonicity) are consequently **Inferred**, not observed.
2. **Migration feasibility.** `implementation-plan.md`'s ordering and `0003_revert` are a design
   argument. No migration was authored, applied, or `sqlmigrate`-rendered. The claim "GMSG-1 can keep
   `student` NOT NULL" is a **proposed** property, not a verified one.
3. **Contract equivalence.** `api.py` was read; `contracts/openapi.json` was not regenerated, so the
   byte-identity claim for GMSG-1 is conditional on the generator behaving as the previous slice
   recorded. Labelled **Inferred**.
4. **Frontend behavior.** The FE inventory is source-level (roles, strings, query keys, freshness
   intervals). No component was rendered. Accessibility statements in `ux-journeys.md` are limited to
   attributes present in JSX and are explicitly **not** an accessibility audit result.
5. **Realtime delivery.** The claim that a hint reaches exactly `recipient_ids` follows from
   `services.py:58-67` + `protocol.py:141-146` + `publish.py:31-40`. No socket was opened, no Redis
   key inspected, so dropped-hint and reconnect behavior is **Unknown**.
6. **Notification silence.** "No message notifications" is a **Verified absence** by enum and call
   search (`notifications/policy.py:42-71`, `services.py:47-67`, no recorder call). It is not proof
   that no template, worker or cron path emits one outside these files; no runtime log was inspected.
7. **Proposal intent.** §18/§19/§26 text was read for scope only. Per §2.9 it is never evidence of
   current behavior, and every "the proposal assumes X" line in `source-lifecycle.md` is paired with
   the code that contradicts or confirms it.
8. **Institutional approval.** Nothing here is GCO/DPO/UCN-approved. Every `D-GMSG-*` recommendation
   is labelled **Provisional — engineering default, not GCO/DPO/UCN-approved**, and `decisions.md`
   ends with the approval gate as a separate section.
9. **Corrections made during the self-audit (Group C), disclosed rather than hidden:**
   - The realtime registry is **5** events at `protocol.py:46-54`, not the "one at `:46-50`" the
     brief stated; Guidance still has exactly one (`:50`).
   - `services.py` exposes **14** public functions, not 12.
   - `continuity_models.py`'s grant spans `:44-190` with a **nullable** `original_counselor`
     (`:49-55`); the brief cited `:44-95` and omitted nullability.
   - My first draft of R-21 called `counseling.shared_summary.published` "not in the registry". It is
     **in the tree** but as a *pre-rename* identifier — live codes are
     `counseling.student_session_summary.published` / `STUDENT_SESSION_SUMMARY`
     (`notifications/policy.py:31,62`), published from `student_session_summaries.py:118`; the old
     codes survive only in cutover-detection predicates
     (`0002_student_session_summary_contract.py:23-25`,
     `preflight_student_session_summary_cutover.py:48-50`). R-21, `README.md` and `current-state.md`
     §9 were rewritten to say that.
   - My first draft of H-3 said College Heads gain messaging reach "through the designation path".
     Wrong: `DESIGNATION_CAPABILITY_GRANTS["HEAD_GUIDANCE_COUNSELOR"]` (`accounts/policy.py:761-782`)
     carries **no** `guidance_messages.*` code; Heads get it from the **COUNSELOR role grant**
     (`:654`, codes `:658-660`) and their multi-College reach from
     `resolve_general_guidance_college_scope`. H-3 was rewritten.
   - 13 relative links in `README.md` pointed one directory too high (`../../../be/…`); corrected to
     `../../be/…` and re-resolved (all 18 targets exist).
   - The proposal's `StudentAffiliation` reference (§19) matches no class in `be/` — recorded as R-20,
     not as an audit error.

---

## 8. Definition-of-done result

| Requirement | Result | Evidence |
|---|---|---|
| All nine files exist under `docs/gmsg-0/` | **Met** | `README.md`, `current-state.md`, `access-matrix.md`, `source-lifecycle.md`, `ux-journeys.md`, `decisions.md`, `implementation-plan.md`, `risks.md`, `validation.md` |
| Only files under `docs/gmsg-0/` created/modified | **Met** | `git status --short` in §4 `[19]` and the final check below shows exactly `?? docs/gmsg-0/` plus the two pre-existing untracked directories; no tracked file modified |
| Start-state gate verified at the required SHA | **Met** | §2 |
| Every substantive claim labelled Verified/Inferred/Unknown with `path:line` | **Met** | Throughout; Unknowns are listed as open items, not guessed |
| Six conversation families covered in the access matrix | **Met** | `access-matrix.md` |
| `D-GMSG-01..18` mapped 1:1 to proposal §26 (8855–8878) | **Met** | `decisions.md`, plus engineering items `D-GMSG-19..30` |
| Migration recommendation with alternatives compared | **Met** | `implementation-plan.md` §1 |
| GMSG-1 plan names exact files, ordering, rollback, tests | **Met** | `implementation-plan.md` §2 |
| Risks include the six named disclosure hazards | **Met** | `risks.md` §2 (H-1…H-7, incl. both realtime and notification hazards) |
| No application code, test, migration, seed, contract, generated client or setting changed | **Met** | §4 Group A; nothing was ever opened for write outside `docs/gmsg-0/` |
| No Git integration | **Met** | No commit, tag, push, checkout, reset, stash, merge or rebase. Only the disclosed `git fetch` (§4) touched `.git` |
| No full test suite; every command recorded | **Met** | §4 (37 invocations), §5 (both failures with stderr), §6 (not-run list) |
| No secrets or PII reproduced | **Met** | No credential, key, production record, Student identity, message body or ciphertext appears in this package; content handling is described by citing `content.py`, never by quoting data |
| Provisional decisions labelled as such | **Met** | `decisions.md` header + the approval-gate section; `risks.md` R-19 tracks the misreading risk |
| Stop conditions evaluated | **Met** | `risks.md` §6: none triggered; GMSG-5 reported **blocked** rather than guessed |
| Changes left uncommitted and unpushed | **Met** | Final state re-checked in §9 |

**Not claimed:** anything requiring execution — migration correctness, constraint enforcement under
concurrency, contract byte-identity, UI behavior, notification absence beyond static search. See §7.

---

## 9. Reproducing this audit

```bash
cd /Users/reynantlntno/Projects/COMPASS
git rev-parse HEAD          # expect de6902200878f1413bea7a5a90166d30be92bdfc
git rev-parse --abbrev-ref HEAD   # expect integration/ux15-modernization
git status --short          # expect only: Claude outputs/, outputs/paper-screenshots/, docs/gmsg-0/
git diff --check            # expect no output, exit 0
```

Then read, in order: `README.md` → `current-state.md` → `access-matrix.md` → `source-lifecycle.md` →
`ux-journeys.md` → `decisions.md` → `implementation-plan.md` → `risks.md`. Every citation is
`path:line` at the SHA above; `risks.md` §7 states how to re-score it at a later commit.

Final end-of-audit check (after writing this file): the package is 9 untracked markdown files under
`docs/gmsg-0/`, and no tracked path in the repository differs from `de690220`.
