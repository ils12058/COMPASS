# Email client readiness

The final campaign reuses the committed synthetic NOTIF-02 and NOTIF-03 preview
corpora (12 + 13 HTML/plain-text pairs, plus suppression/status JSON). They account
for all seven Appointment and eight additional operational events, Student/Counselor/
former-Counselor cases, minimal, absent/unauthorized source, legacy and suppressed
examples. They are explicitly reused examples, not freshly delivered emails.

The coordinated backend suites freshly validate both policies, template parity,
private-field exclusion, origin/source/recipient changes, malformed values, HTML
escaping and source suppression. Existing preview cases include long labels, missing
optionals and Philippine-Time/cross-date formatting. Suppressed messages have no
invented HTML body. Subjects/preheaders are fixed code-owned copy.

`notification-email-layout.browser.mjs` checks every saved HTML file at 390/680px
in Chromium and WebKit: no document overflow, script/iframe/embed/image/external
stylesheet resources, unexpected origin or mismatch with the plain-text action URL.
It blocks all network requests; no tracking image or remote mail resource is used.
Screenshots and per-layout results are indexed in evidence. This is browser layout,
not native Gmail/Outlook rendering or delivery proof.

## Controlled manual checklist — all Not executed

| Check | Procedure / expected result | Status |
| --- | --- | --- |
| SMTP safety prerequisite | Separately authorize synthetic staging mailbox, worker version/profile/origin and recipient allowlist | Not executed |
| SMTP handoff/retry | Exercise accepted/failed/zero/duplicate/recovery attempts against controlled transport; SENT is handoff only | Not executed |
| Gmail web/mobile | Inspect all 15 event meanings, safe CTA and plain-text alternative, long labels/URLs at desktop/phone widths | Not executed |
| Outlook desktop/web | Inspect table wrapping, styles stripped, CTA visibility and literal plain-text link | Not executed |
| Phone mail apps | Inspect touch action, wrapping, local-time labels, cross-date interval, light/dark preferences | Not executed |
| Spam/inbox acceptance | Confirm sender/authentication/inbox behavior in controlled mailbox; no claim from locmem | Not executed |
| Screen readers | Read heading/rows/action/footnote without reliance on color and confirm understandable ordering | Not executed |
| Revoked/former recipient | Copy link to unrelated/revoked synthetic account and verify normal safe record denial | Not executed |
| Institutional copy review | Approve the exact full operational_v1 four-family fields, roles, fallback/suppression and mailbox risk | Requires institutional approval |

Do not send real rich mail or use institutional Student records to complete this list
without separate authorization. Accepted messages cannot be recalled or treated as
proof of recipient reading. Do not infer Registrar dry sealing or payment completion.
