# Future institutional UAT — NOT EXECUTED

Every script below is **NOT EXECUTED**. Do not mark PASSED using engineering tests. An institutional
UAT lead must first approve environment, synthetic/scrubbed data, actors, Catalog grants, academic
policy, evidence retention and permitted actions. Do not use real Students or grant actual authority
under this document alone. Stop on an unexpected privacy disclosure, unexplained persisted change
or unresolved security conflict; record an issue without continuing consequential operations.

For each task record: execution date/time/timezone; approved candidate SHA/artifact/environment;
operator and approver; synthetic actor/session identifier (no cookie/code/password); target UUID/code;
pre/post version/state; request correlation; Audit event/actor/basis; screenshot or observation;
expected versus observed; PASS/FAIL/NOT EXECUTED; issue reference and retest approval. Include human
keyboard/screen-reader/native zoom/device observations where applicable. Never store secret TOTP
material or confidential answers in the UAT evidence package.

| # | Task script | Expected result / specific evidence |
|---|---|---|
| 1 | Approved Catalog-only manager signs in with actual security flow; open Structure and try relationship URL | Catalog actions available; relationship administration denied; record effective capabilities/HTTP outcome |
| 2 | Relationship-only manager opens Structure, Responsibilities and Student Affiliations; attempt direct Catalog edit | Existing relationship workflows available; no Catalog edits/history; record denial and unchanged DB |
| 3 | Approved staff reference reader browses hierarchy and direct history/mutation URLs | Read-only structure; protected requests denied without private data |
| 4 | Synthetic Student opens standalone Organization and attempts Catalog requests | Workspace unavailable; no mutations/history; selector contract stays usable |
| 5 | Create approved synthetic Campus code/name/status/basis; attempt normalized duplicate | One stable UUID/version 1/event; duplicate refused, draft retained |
| 6 | Add College in known Campus; repeat with inactive parent | Parent fixed; active creation under inactive Campus refused |
| 7 | Add complete active Program, then inactive pending Program | Complete policy required for active; no inferred classification/levels; pending draft stays inactive |
| 8 | Update complete policy to approved noncontiguous set; repeat no-op; try with pending F4 | Exact set/version/Audit; no-op silent; pending-F4 refusal has no override |
| 9 | Rename each institutional definition | Same UUID/code/parent; one version/event; current joins change, saved facts remain |
| 10 | Two administrators review the same record; save one then confirm the other | Stale edit refused; local input preserved, current comparison loaded; deliberate new review |
| 11 | Let recent MFA expire during editing; change target from another session, verify authenticator | No captured mutation replay; draft retained; refresh/re-review and second confirmation required |
| 12 | Create code with case/outer-space equivalent under same parent, then legitimate different parent | Same-parent duplicate refused; identity scope correctly explained; no code reuse of retired row |
| 13 | Preview Campus retirement with active children/live work; try direct mutation | Actual blockers shown; backend refuses; no cascade/relationship rewrite |
| 14 | Retire College with active Program/Student/responsibility/open Office/pending Follow-Up | Specific blocker counts, no confidential detail, unchanged persisted state |
| 15 | Retire Program with submitted history/draft/pending Good Moral | Existing warnings preserved; allowed when contract permits; current new selection/submission refuses inactive ancestry |
| 16 | Compare explicit Counselor, unique Head fallback and GSS supervision scope before/after accepted edits | Routing/scope preserved; inactive/ambiguous configuration fails closed; no extra confidential access |
| 17 | Retain inactive account affiliation through permitted retirement; attempt reactivation | Relationship retained; unsafe account restoration refused with remediation conflict |
| 18 | Draft/submit Inventory with configured valid/invalid and pending/unknown levels | Current policy/ancestry enforced; compatibility understood; submitted course/year/answers/timestamp unchanged |
| 19 | Exercise F4 Bachelor/Years 1–4 exclusions and F6 historical degree text; existing GM-OR receipt workflow | No Year-5/template expansion; F6 not whitelist; receipt/fee/inspection/issuer constraints preserved |
| 20 | Open exact-target history, page, compare authenticated actor/versions/basis; try unauthorized actor | Correct bounded committed facts, no global Audit/private details; direct denial |
| 21 | Retrieve authorized existing synthetic F4/F6 PDF before/after Catalog edits and invoke native print | Saved applicant/degree/receipt/issuer/date/template facts and presentation retained; record page/print observations, no reissue |
| 22 | Under separately approved recovery plan, rehearse uncertain saved response and consistent DB/Audit restore; reconcile post-backup commits | No duplicate mutation/false success; retained UUIDs/policy/versions/receipt/history; compatible artifacts; authority owner approves resumption |

Additional accessibility evidence fields: actual screen reader/browser/version, actual native 200%
zoom setting, keyboard path/focus/announcement observations, physical device/viewport and long
name/history/impact examples. A CSS font-size test must not populate native-zoom completion.

UAT acceptance requires identified institutional owners, issue resolution and signed evidence for
all applicable scripts. Deployment, production promotion and operational Catalog activation each
require their own approval after UAT; this package executes none of them.
