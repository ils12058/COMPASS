# Integration manifest

| Component | PR | Verified merged integration commit | Reviewed implementation head |
| --- | --- | --- | --- |
| NOTIF-01 secure links/presentation | [#310](https://github.com/ils12058/COMPASS/pull/310) | `6f73efd981023a29fef0b0ea10ecbaacbe16212b` | `d860ff0afcca8d322e9b292ccff60a87e48d3b00` |
| NOTIF-02 seven Appointment events | [#311](https://github.com/ils12058/COMPASS/pull/311) | `6d6f3e0accbef09302f6b158295632059b9ff211` | `1a02649cc0f61c4f01f9927979ccc1a6070e0f3b` |
| NOTIF-03 central policy/eight events | [#312](https://github.com/ils12058/COMPASS/pull/312) | `f0b05dcf6a2a80e22193144891d23fee5865bdad` | `0fb31c0b7c814cb67077ace765de559ec4c2af3d` |
| NOTIF-04 final integration | [#313](https://github.com/ils12058/COMPASS/pull/313) | PR head includes implementation plus evidence metadata | `38f632ae70073861f480500be1664c4af9b67eb7` (implementation/audit commit) |

Fresh fetch before branching verified integration at `f0b05dcf6a2a80e22193144891d23fee5865bdad`,
staging at `0a843dae20c01984d0fb9aa46d5eef34102ab386`, and main at
`1a9933535a0b8c0cbd7764c35f301e8402f48375`. All three dependency merge commits
are ancestors of the new worktree HEAD. Primary checkout stays on staging; its
preexisting untracked files were not touched.

Worktree: `~/.codex/worktrees/notif-04-cross-channel-hardening/COMPASS`.

## Changed subsystem inventory

- Five frontend production files: login transition URLs, server pages for MFA verify/setup,
  and restart-link handling in the existing MFA components.
- Backend `test_notification_cross_channel.py`, registered in the existing notifications
  CI bundle; no workflow trigger/filter changes.
- Focused frontend route-contract tests and shared 22-case route fixture, expanded
  auth browser suite, new Notification Center/browser and email-layout suites.
- This documentation/evidence package. No models, migrations, OpenAPI, domain
  producers, queues, templates, channel policy or rich disclosure fields change.

Configuration dependencies: one `COMPASS_EMAIL_DISCLOSURE_POLICY` (default minimal),
validated optional `COMPASS_PORTAL_ORIGIN`, obsolete key removal, consistent reviewed
backend/worker versions. See [cutover](configuration-cutover.md). The frontend MFA
correction requires a separately authorized frontend rollout to take effect.

Local environments reuse installed dependency runtimes, with a dedicated synthetic
PostgreSQL test database. No live environment was inspected or modified.

## Published review state

PR [#313](https://github.com/ils12058/COMPASS/pull/313) is open, non-draft, unmerged,
and targets `integration/ux15-modernization`. GitHub reports mergeable. At the
published implementation head `38f632ae70073861f480500be1664c4af9b67eb7`, the
connector reports **zero commit statuses and zero workflow runs**. Relevant hosted
filters exclude this integration target; this is not a CI-green claim. No workflow
was dispatched. A final evidence-metadata commit adds this PR reference; the final
agent report records and verifies the resulting exact local/remote PR head.

Before publication, a fresh fetch reverified the starting integration, staging and
main SHAs above without changes. No protected ref, deployment, merge, live setting,
SSH, DigitalOcean/Vercel operation or real outbound mail was performed.
