# FAC-3 Faculty Portal

Implemented from integration `1a8f9aa3`, after merged FAC-1 (#348) and FAC-2 (#349).
Branch: `codex/fac-3-faculty-portal`; PR target: `integration/ux15-modernization`.
No deployment or live institutional activation is included.

The Faculty Portal now has a finished unavailable Home and a policy-ready digital
Referral workflow. Its authorized experience confirms one exact Student ID,
captures Course/Year/Block and reason, reviews them, submits once, and shows the
canonical reference/time/Student name/Submitted result. My Referrals and details
use only the Faculty own projections. Notifications and My Profile reuse their
existing account destinations; current home College remains read-only.

**The default service is still unavailable.** FAC-2's real approval providers still
return `None`. Neither capability grants nor frontend state activates lookup,
submission or own-record disclosure. Successful own-list access is independent of
permission for a new submission. Positive browser evidence uses synthetic approved
policies in a disposable database, never an institutional approval.

| Destination | Route | Authority before mounting its record/form queries |
| --- | --- | --- |
| Faculty Home | `/portal` | Existing authenticated Faculty session |
| Submit Referral | `/portal/faculty/referrals/new` | Faculty role plus both narrow capabilities; positive separate lookup/submission availability before exposing a new form |
| My Referrals | `/portal/faculty/referrals` | Faculty role and own-read capability; current own-read availability |
| Referral details | `/portal/faculty/referrals/{id}` | Faculty role and own-read capability; backend current policy and immutable ownership decide every read |
| Notifications | `/portal/notifications` | Existing Notifications Center |
| My Profile | `/portal/account/profile` | Existing own Profile, including managed home College |

The outer Portal boundary refuses Faculty access to GCO/clinical/administrative
workspaces and refuses other roles access to the Faculty namespace, before those
components mount. The dock and command palette expose Faculty actions only when
current capability and availability facts permit them. Their existing behavior
for other roles is preserved.

See [preflight and decisions](architecture.md), [validation](validation.md),
[screenshots](screenshots.md), and [FAC-4 handoff](handoff.md).
