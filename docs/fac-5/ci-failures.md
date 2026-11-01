# Resolved CI failure matrix

Baseline is FAC-4 implementation `2aed08ac` / integration squash `d9971e89`.
Hosted failures were inspected at backend run [41252323738](https://github.com/ils12058/COMPASS/actions/runs/41252323738)
and frontend run [41252325881](https://github.com/ils12058/COMPASS/actions/runs/41252325881),
with matching FAC-3 base evidence in runs 41249274723 / 41249277319.
Current unchanged failures were reproduced locally before correction.

| Failure / owner | Verified cause | Correction and retained contract | Local verification |
|---|---|---|---|
| Privacy notice page query budget / Authentication + Privacy | AuthSession selected User but lazily fetched its Role, producing 8 queries | Join User.Role in existing authenticated lookup; retain maintenance/session and all three capability sources, bounded revision prefetch and unchanged maximum 7 | Existing privacy contract suite passes; no threshold increase |
| Summary regeneration lock scope / Counseling | Joined Student/Counselor query used unrestricted FOR UPDATE | FOR UPDATE OF self on the Encounter; retain dataset exclusion, explicit synthetic scope/approval, canonical ciphertext and transactional publication | Lock inventory and summary-cutover tests pass |
| AuthSession revocation source inventory / Realtime + Counseling | Regex treated Case Coverage grant.revoked_at as an AuthSession writer | Verify canonical CounselorCaseContinuityGrant import/bindings and exactly its single assignment; any additional/unknown writer still fails. Existing AuthSession socket-close primitive unchanged | Full realtime-ticket and continuity tests pass |
| Organization 0002 reversal / Migration assurance | Shared-database rollback rehearsal crossed an intentionally irreversible policy migration | New owned database starts at supported floor, upgrades forward, compares every old column, rolls back a simulated failed transaction and reapplies forward migrations; no installed history reversed | Disposable PostgreSQL forward rehearsal passes; Faculty migration guards remain intact |
| E-Counseling narrow-phone tray / E-Counseling UI | Repeated self/status rows pushed stage to 345px on 640px viewport | Group existing identity/status metadata compactly without hiding identity, consent or call controls; keep original half-screen and 44px controls assertions | 40/40 Call browser cases in each engine |
| Retention Policies hierarchy / Privacy UI test | Fine-pointer Help uses an accessible icon with no visible text | Assert one correctly named Help control and its 44px target, read-only semantics and no mutation; retain all policy wording checks | 18/18 hierarchy cases per engine |
| UX-P2A action surfaces / Shared UI test | Obsolete 48px decorative icon-square assertion predates SIMPLIFY-3's labeled control | Check full interactive control >=44px, visible label, decorative icon, links, rail placement, focus and reflow against current AGENTS contract | 6/6 P2A cases per engine |
| Routine Intake label / Routine UI test | Exact Save progress casing differed from current Save Progress | Use the actual current action label; keep draft editability, hidden Counselor fields and no confidential workspace links | Included in P2A pass |
| Feedback / Client Satisfaction Measurement error copy / Feedback UI test | Old error-dialog expectation predates canonical uncertain-save recovery | Assert one polite uncertain status, closed confirmation, preserved/disabled fields, current status read, explicit status/retry actions and exactly one POST; no unsafe auto retry | 44/44 user-copy cases per engine |
| New expanded 200% matrix / Referral + shared record layout | Viewport-based GCO rail and four-column facts ignored narrow available width; status wrapper refused shrinking | Available-width container breakpoints for rail/facts and bounded status wrapping; original overflow checks retained | Expanded Faculty/GCO suite 108/108 per engine |
| Persistent-call Routine save selectors / E-Counseling UI test | Exact old Save evaluation/Save progress and Saved strings predated current labels/status | Select Save Evaluation/Save Progress and the actual polite Evaluation progress saved status; retain same audio element, track ownership, single join/token, capture and dock clearance checks | 17/17 runtime cases per engine |
| UX-P1 action contract and Appointment rail / Appointments + UI test | Old decorative 48px assumptions; 7rem rail left only 60px for Open Counseling, splitting it into three lines | Assert accepted full labeled 44px control; widen only the Appointment rail to 10rem. Retain two-line label, actual resource links, PDF pending state, Messages side-by-side and overflow checks | 16/16 P1 cases per engine |
| Public-shell WebKit Escape focus / Public + Accessibility UI | Native popover close/focus sequencing did not reliably return focus; delayed Accessibility focus could compete with native default | Handle Escape explicitly: prevent competing default, close native popover, focus its actual trigger. Opening mobile navigation focuses its first link. Native outside dismissal and real navigation remain | 21/21 public-shell width/text/focus cases per engine |
| WebKit reload runtime errors / Email/session browser fixtures | Test-triggered hard reload cancelled router RSC prefetches, reported as access-control page errors; raw synthetic-only diagnostic reproduced the affected paths | Wait for the existing bounded fetch-settling helper before the test's reload. Do not filter, ignore or clear errors; zero-runtime-error and all auth/destination/MFA assertions remain | Email change 11/11 and email auth 21/21 per engine |

| Hosted browser dependency installation / CI infrastructure | Backend job 124708430521 made no progress after APT index fetches at 00:59:42 UTC until superseded/cancelled at 01:20:50; no tests ran in that job | On disposable Linux Actions runners replace only the Azure mirror URI with official HTTPS Ubuntu archive, bound connection/data waits to 30s with two retries and browser install to 10 minutes. Keep suites, components, keys, TLS/signature checks, frozen dependencies and every test | Shell syntax and planner checks pass; final exact-head hosted install/tests are the acceptance gate |

The four original backend cases failed in a 26.95s unchanged local reproduction.
The corrected synthetic baseline browser counts were 39/40, 17/18, 1/6 and 40/44;
all corresponding current focused suites pass. Normal-build fake-call failures and a local
build/start sequencing error were excluded from regression evidence and rerun correctly.

The first FAC-5 hosted frontend run [41258967835](https://github.com/ils12058/COMPASS/actions/runs/41258967835)
on implementation `480da90d` exposed the four follow-up rows above. Its static/unit/build and
five of eight browser shards passed; the three failed shards were investigated before the
updated exact-head rerun. All five affected full suites now pass locally in both engines.

The committed local reports contain passing final cases only, with no raw request bodies,
credentials or SQL row values. Hosted CI runs the complete planned suites independently.
Exact-head hosted results and any newly discovered regression are recorded in the PR's
CI/readiness section; local results alone do not certify the whole pipeline. Cancelled or
unexecuted jobs remain incomplete, regardless of successful build/unit jobs.

No known failed assertion was removed or weakened. No production approval, grant, clinical
lifecycle, migration history, live Notification behavior or deployment setting is changed.

## CI dependency evidence and bounded correction

The initial backend run's [shard 4](https://github.com/ils12058/COMPASS/actions/runs/41258965387/job/124708430521)
started its installer at 00:59:22 UTC. Its final APT progress was at 00:59:42, with Azure
package-index requests ignored and archive fallback fetches, followed by no progress before
our final-head dispatch superseded it at 01:20:50. This is an observed repository-fetch stall,
not a failed backend assertion. Shard 1 printed 1,064 passing tests/two skips but was cancelled
during completion; it is still not an accepted successful job. Shards 2/3/6 passed normally.

The shared CI-only helper changes only the known Azure mirror URI in the runner's existing
mirrorlist, retaining other entries/metadata and the existing Ubuntu suite/signing configuration.
APT's [mirrorlist format](https://manpages.ubuntu.com/manpages/noble/man1/apt-transport-mirror.1.html)
and [connection/data timeout](https://manpages.debian.org/bookworm/apt/apt-transport-http.1.en.html)
are documented by their maintainers. The helper applies [APT retry/configuration options](https://manpages.debian.org/bookworm/apt/apt.conf.5.en.html),
requires a disposable Linux Actions environment and does not run on application/deployment hosts.
Targeted backend, full backend and frontend browser jobs use the same preparation, with a
10-minute install-step bound. Install errors still fail the job and no test is bypassed.
The final exact implementation must pass both backend workflows and the complete frontend
workflow; intermediate cancelled runs never substitute for that final gate.
