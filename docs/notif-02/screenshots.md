# Synthetic preview index

All fixtures come from isolated local tests, not institutional records. The portal
is the reserved `https://portal.example` origin, references/names are synthetic and
dates are in 2099. Each status record marks `synthetic: true` and `transport: not_sent`.
HTML/text use the real resolver and templates. The deliberately private Student
fixture name never appears in the delivered content.

| Scenario | HTML | Plain text | Resolution |
| --- | --- | --- | --- |
| Scheduled Student | [HTML](previews/scheduled-student.html) | [Text](previews/scheduled-student.txt) | [Status](previews/scheduled-student.json) |
| Scheduled current Counselor | [HTML](previews/scheduled-counselor.html) | [Text](previews/scheduled-counselor.txt) | [Status](previews/scheduled-counselor.json) |
| Single valid reschedule | [HTML](previews/rescheduled-student.html) | [Text](previews/rescheduled-student.txt) | [Status](previews/rescheduled-student.json) |
| Reassigned Student | [HTML](previews/reassigned-student.html) | [Text](previews/reassigned-student.txt) | [Status](previews/reassigned-student.json) |
| Former Counselor minimal | [HTML](previews/reassigned-former-counselor.html) | [Text](previews/reassigned-former-counselor.txt) | [Status](previews/reassigned-former-counselor.json) |
| Cancelled | [HTML](previews/cancelled-student.html) | [Text](previews/cancelled-student.txt) | [Status](previews/cancelled-student.json) |
| Automatic 24h | [HTML](previews/reminder-24h.html) | [Text](previews/reminder-24h.txt) | [Status](previews/reminder-24h.json) |
| Automatic 3h | [HTML](previews/reminder-3h.html) | [Text](previews/reminder-3h.txt) | [Status](previews/reminder-3h.json) |
| Manual reminder | [HTML](previews/reminder-manual.html) | [Text](previews/reminder-manual.txt) | [Status](previews/reminder-manual.json) |
| No disclosure approval | [HTML](previews/minimal-no-approval.html) | [Text](previews/minimal-no-approval.txt) | [Status](previews/minimal-no-approval.json) |
| Superseded change | Suppressed: no email | Suppressed: no email | [Status](previews/suppressed-superseded.json) |
| Long Service/provider names | [HTML](previews/long-labels.html) | [Text](previews/long-labels.txt) | [Status](previews/long-labels.json) |
| Missing optional labels | [HTML](previews/missing-optionals.html) | [Text](previews/missing-optionals.txt) | [Status](previews/missing-optionals.json) |

Chromium examined every HTML fixture at 390px and 680px (24 layouts), blocked
network requests, checked no horizontal overflow and rejected scripts/images/
frames/stylesheets/objects/embeds or hrefs outside the reserved portal's closed
Appointment UUID route. This is local HTML evidence, not actual mail-client proof.

Saved screenshots:

- [Scheduled Student mobile](previews/screenshots/scheduled-student-390.png)
- [Scheduled Student desktop](previews/screenshots/scheduled-student-680.png)
- [Current Counselor desktop](previews/screenshots/scheduled-counselor-680.png)
- [Rescheduled Student mobile](previews/screenshots/rescheduled-student-390.png)
- [Former Counselor minimal mobile](previews/screenshots/reassigned-former-counselor-390.png)
- [Long labels mobile](previews/screenshots/long-labels-390.png)
- [Missing optionals mobile](previews/screenshots/missing-optionals-390.png)

Desktop standard and mobile long-label images were visually reviewed: readable
facts/action, no clipping or overflow; long values extend vertically. Remaining
cases have automated DOM/layout checks and saved examples. No claim is made about
Gmail, Outlook, deliverability, spam filtering or external accessibility tooling.
