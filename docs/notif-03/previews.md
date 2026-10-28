# Synthetic operational email evidence

All examples come from the actual typed resolvers/templates with isolated local
database sources and locmem/mocked transport. They use reserved `.example` portal
URLs, synthetic identities/labels and future 2099 Group Session schedules. Good
Moral issuance uses the synthetic test's local issuance timestamp. No institutional
mailbox or real Student record is used. Status files mark `synthetic: true` and
`transport: not_sent`; they are not SMTP or deployment evidence.

| Scenario | HTML | Plain text | Resolution |
| --- | --- | --- | --- |
| Group registration confirmed, approved profile | [HTML](previews/group-registered.html) | [Text](previews/group-registered.txt) | [Status](previews/group-registered.json) |
| Group registration cancelled | [HTML](previews/group-registration-cancelled.html) | [Text](previews/group-registration-cancelled.txt) | [Status](previews/group-registration-cancelled.json) |
| Group Session cancelled | [HTML](previews/group-cancelled.html) | [Text](previews/group-cancelled.txt) | [Status](previews/group-cancelled.json) |
| Group Session latest reschedule | [HTML](previews/group-rescheduled.html) | [Text](previews/group-rescheduled.txt) | [Status](previews/group-rescheduled.json) |
| Good Moral assisted creation | [HTML](previews/good-moral-assisted.html) | [Text](previews/good-moral-assisted.txt) | [Status](previews/good-moral-assisted.json) |
| Good Moral issued | [HTML](previews/good-moral-issued.html) | [Text](previews/good-moral-issued.txt) | [Status](previews/good-moral-issued.json) |
| LIVE Call Slip issued | [HTML](previews/call-slip-issued.html) | [Text](previews/call-slip-issued.txt) | [Status](previews/call-slip-issued.json) |
| LIVE Call Slip voided | [HTML](previews/call-slip-voided.html) | [Text](previews/call-slip-voided.txt) | [Status](previews/call-slip-voided.json) |
| Minimal policy, authorized link | [HTML](previews/minimal-link.html) | [Text](previews/minimal-link.txt) | [Status](previews/minimal-link.json) |
| Missing legacy source | [HTML](previews/missing-source.html) | [Text](previews/missing-source.txt) | [Status](previews/missing-source.json) |
| Unauthorized recipient | [HTML](previews/unauthorized-recipient.html) | [Text](previews/unauthorized-recipient.txt) | [Status](previews/unauthorized-recipient.json) |
| Superseded reschedule | No email: suppressed | No email: suppressed | [Status](previews/superseded-session.json) |
| Long sensitive title and missing venue, both omitted | [HTML](previews/long-sensitive-title-omitted.html) | [Text](previews/long-sensitive-title-omitted.txt) | [Status](previews/long-sensitive-title-omitted.json) |
| Legacy unknown void, minimal | [HTML](previews/legacy-void-minimal.html) | [Text](previews/legacy-void-minimal.txt) | [Status](previews/legacy-void-minimal.json) |

There are 13 HTML/text pairs and 14 resolution records. The obsolete case has no
fabricated body. All dynamic details and destinations agree between alternatives.
Private fixture markers and unsafe title/meeting content are absent from subjects,
preheaders, bodies and plan reprs. Trailing whitespace is normalized only when
writing review fixtures, not in transport rendering.

## Local layout checks

Chromium rendered all 13 bodies at 390px and 680px: **26 layouts passed**, with
network requests blocked, no horizontal overflow, no script/image/frame/stylesheet/
object/embed resources and no href outside the three reserved closed record routes.
Saved full-page screenshots:

- [Group registration mobile](previews/screenshots/group-registered-390.png)
- [Group registration desktop](previews/screenshots/group-registered-680.png)
- [Cancelled session mobile](previews/screenshots/group-cancelled-390.png)
- [Good Moral issued mobile](previews/screenshots/good-moral-issued-390.png)
- [Call Slip voided mobile](previews/screenshots/call-slip-voided-390.png)
- [Long sensitive title safely omitted](previews/screenshots/long-sensitive-title-omitted-390.png)
- [Minimal authorized link](previews/screenshots/minimal-link-390.png)

The Group desktop and Good Moral mobile images were visually inspected: clear
event wording, readable rows/action, no clipping or private fields. Long source
titles never enter the layout. This does not certify Gmail/Outlook, delivery,
spam filtering, screen-reader behavior or a complete authenticated browser flow.
Those remain [follow-ups](followups.md).

Reproduce source previews from `be/` with:

```sh
COMPASS_OPERATIONAL_EMAIL_PREVIEW_DIR=../docs/notif-03/previews \
POSTGRES_USER=reynantlntno POSTGRES_PASSWORD=unused POSTGRES_DB=compass_notif03 \
  .venv/bin/pytest tests/test_operational_email_presentation.py \
  -k synthetic_operational_previews -q --reuse-db
```

Without the explicit output environment variable, tests use pytest temporary
directories. No preview command invokes delivery or creates another event intent.
