# External Appointment disclosure policy

> Historical NOTIF-02 configuration: superseded by NOTIF-03. The original
> `APPOINTMENT_EMAIL_DISCLOSURE_POLICY` name below is retired and now rejected.
> Current operations must use `COMPASS_EMAIL_DISCLOSURE_POLICY`; approval covers
> the complete four-family bundle. See [current policy](../notif-03/centralized-disclosure-policy.md).

`APPOINTMENT_EMAIL_DISCLOSURE_POLICY=minimal` is the default. Only the exact
version `operational_v1` selects the reviewed code-owned field bundle. Unknown,
empty, differently cased or non-string override values downgrade to minimal.
No user preference, request, frontend flag or arbitrary list enables fields.
Selecting this version in a future deployment requires prior institutional
authorization of the exact bundle; this PR does not establish that approval.

## Recipient allowlist

| Class | Details permitted by version 1 | Links |
| --- | --- | --- |
| Current Student owning Appointment with actual source access | Reference, Service-name snapshot, date/time or exact previous/updated schedule, mode, current assigned/new Counselor name where appropriate | Existing trusted APPOINTMENT route, current authorization required |
| Current assigned Counselor with actual source access | Reference, Service-name snapshot, date/time or exact previous/updated schedule, mode | Same authorized record link |
| Previous Counselor for a reassignment source | Existing minimal fixed notice only, even with independent management scope | None |
| GSS | No rich field bundle; no new recipient | Existing scoped NOTIF-01 Scheduled pilot link only |
| Unrelated, inactive, role/capability/scope-ineligible | No protected fields | None; inactive transport is cancelled |

No Student name, institutional ID, contact information or academic/profile facts
exist in the email detail vocabulary. Assigned Counselors also do not receive
provider names in their field bundle. Cancellation omits provider-name context.
Student notices never include previous-provider names in version 1. Current names
are labeled as such; historical name snapshots do not exist in the source.

Source ownership and normal detail authorization are checked from a freshly
loaded actor. Notification ownership alone grants nothing. Previous-provider
classification is based on that exact source event, before considering unrelated
management authority. The normal record endpoint independently authorizes any
later click, including after access changes. No magic link or auth token exists.

## Data boundary

Appointments produces frozen typed facts/rows. Fields are closed enums; values
are bounded plain strings (not SafeString/HTML objects), with no controls or URI/
email-address-like content. Unsafe optional labels are omitted. HTML autoescaping
remains enabled. Plain-text detail rendering preserves literal characters through
its text-only partial; it never interprets markup. No user data reaches subjects,
preheaders, template paths, HTML attributes other than the rebuilt trusted href,
or arbitrary query parameters.

Prohibited regardless of approval version: Counseling/Referral narratives,
Evaluation or Routine Interview answers, assessment findings/scores, Follow-Up or
private Message content, reasons/internal remarks, handoffs, online joining URLs,
E-Counseling tokens, media/transcripts, financial/OR data, passwords, OTPs, MFA/
recovery/session secrets. Service description, private change reason and whole
User/Appointment/change/occurrence records never reach templates.

## Final revalidation and logs

The existing worker re-resolves the plan after rendering, checking current account
email/activity, source/revision/relationship, capabilities/scope, policy version,
actual disclosed rows and trusted link. Revocation or changed safety facts cancels
before transport. Nondisclosed name changes or unrelated metadata do not enter
equality, so they cannot arbitrarily cancel an otherwise stable message.

Facts, targets, row values and validated URLs stay out of reprs and logs. Existing
bounded delivery identifiers/reason codes remain the diagnostics; no body, account
email, source detail or raw exception text is logged. An external email already
accepted cannot be revoked, and a read-to-SMTP race cannot be made atomic. This
limit is not institutional permission to widen disclosure.
