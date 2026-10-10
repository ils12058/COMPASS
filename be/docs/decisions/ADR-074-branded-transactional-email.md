# ADR-074: Branded transactional email presentation

- Status: Accepted
- Date: 2026-10-04
- Extends: ADR-041 (Notifications and email delivery), ADR-046 (Notification domain integrations),
  ADR-049 (previous-address email-change alert)
- Preserves: event policy, recipients, optional-email preference, EmailDelivery persistence,
  retry/claim behavior, Email OTP security properties, and the no-frontend-URL rule

## Context

Notification email already sent `text/plain` plus `text/html`. However, the shared HTML base was
an unstyled `<main>`, so HTML mail looked like a raw system message. The two direct
authentication emails, Email OTP and the alert to the previous sign-in address after an email
change, sent plain text only. Each built its body as an inline string in a Celery task.

An inventory of every send path found exactly three producers, all through `Mailer`:

- `notifications.delivery.deliver_email_delivery`, covering 18 email-enabled events;
- `authentication.tasks.deliver_email_otp`, covering the email verification, recovery, security
  challenge, and email-change purposes;
- `authentication.tasks.deliver_email_change_security_alert`.

`Mailer.probe_connection` opens and closes the transport without sending. Django error mail is
not configured: there are no `ADMINS`, and the `django` logger writes to the console only.

## Decision

**One shared, code-owned shell.** `compass/common/templates/compass/email/` holds the shells:

- `base.html` and `base.txt` for ordinary messages;
- `security.html` and `security.txt` for the "Security notice" variant.

`TEMPLATES["DIRS"]` adds that directory. Authentication and Notifications can then both extend
it, without Authentication depending on the Notifications app and without a new installed app.
The shared shell replaces the old unstyled `notifications/email/base.html`.

**Small event templates.** Each message is a `<name>.txt` and `<name>.html` pair that supplies
only a preview line, a heading, and its approved wording. `compass.common.email.render_email`
renders both bodies with the same context. Notification templates receive only the code-owned
subject, never Notification rows or source-domain records, so styling cannot widen disclosure.
`RenderedEmail` keeps bodies out of its `repr`.

**Presentation:**

- **Header.** A text-only institutional header: COMPASS, University of Camarines Norte, Guidance
  and Counseling Office. It sits on the brand maroon `#6b1f2a` with a thin `#936515` gold rule.
- **Card and footer.**
  - A 600 px white content card on cream `#f7f3ea`.
  - Headings in strong maroon `#4d1520`; body text `#222a2d`.
  - Footer: "This is an automated COMPASS message." in `#555d60`.
- **Security variant.** A small gold "Security notice" label, with no red banners.
- **Markup.** Table layout, inline styles, system fonts, `color-scheme: light`, a hidden preview
  line, and one `@media` rule for narrow screens.
- **Excluded.** Images, links, remote resources, web fonts, and scripts.

Every message stays readable when a client strips the `<style>` block or all styling.

**Security email:**

- The Email OTP is multipart. Its HTML shows the exact six digits in one selectable text node.
  Spacing is CSS `letter-spacing` only, so a copied code pastes into COMPASS unchanged.
- The code is still never persisted, logged, linked, or placed in audit or Notification data. A
  rendering failure sends nothing and logs only the challenge ID, so the code cannot reach worker
  failure logs.
- The previous-address alert is multipart, keeps its approved wording and durable single-send
  recovery, and names neither address nor the actor.

**Unchanged:**

- Subjects.
- `Mailer` stays transport-only and gains nothing.

**Previews.** `render_email_previews --output-dir <dir>` writes every message to local files and
sends nothing.

## Consequences

- New email events must add a template pair. A catalog test fails when an email-enabled event
  lacks either template, when an orphan template exists, or when the HTML and text wording
  diverge.
- Rounded corners, the `@media` gutter, and the hidden preview line are progressive
  enhancements. Clients without support, such as Outlook for Windows, show square corners and
  desktop padding.
- Plain-text bodies now end with the same institutional footer as the HTML.
- A canonical frontend URL for deep links remains a separate, deployment-owned decision.
