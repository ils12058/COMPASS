# Recipient-safe email presentation

`NotificationEmailPresentation` is a frozen, slotted rendering plan containing
only `event_code`, an `EmailPresentationReason`, optional recipient class and a
closed `NotificationEmailTarget`. `suppress` derives from `source_stale`.
The target is excluded from repr. The builder's URL is also excluded from repr.

No free subject, heading, HTML, template path, message, detail dictionary or
source model is part of the contract. The renderer selects subject/template from
the existing code-owned event catalog. Only `appointment.scheduled` can provide
an Appointment action; mismatched events, untyped plans and inconsistent
action/reason combinations are rejected. It rebuilds the URL through the trusted
link builder. An invalid target/configuration cannot inject an HTML href.

The only new template value is `action_url`; both alternatives receive this same
validated string. HTML autoescaping remains on. The action label, explanatory
copy and footnote are fixed. No detail rows are implemented before a real approved
requirement exists. The shared renderer and institutional shells remain in use.
Generic `render_notification_email(event_code)` still passes subject only and
works for static previews and existing callers. OTP and previous-email-address
alerts keep their specialized paths.

## Four separate decisions

1. **Minimal notice eligibility:** existing event/channel/preference and source
   currentness policy. Safe historic notice ownership does not grant detail access.
2. **Detail disclosure:** no source detail is approved in NOTIF-01; always absent.
3. **Email link eligibility:** the source and target must match the enabled event;
   current account, normal domain authorization, recipient classification and
   upcoming state are evaluated during resolution and immediately before send.
4. **Opening later:** the destination's normal session and record authorization
   run again, independent of the email's earlier eligibility.

Appointments owns `scheduled_appointment_email_access(appointment_id,
recipient_id)`. It loads a fresh actor and calls the normal Appointment detail
service. The Student must still have current relationship/capability; the current
provider must be a Counselor with current access. GSS additionally needs actual
operational scope through the existing management policy. Former/unrelated
Counselors get no link in this pilot, even if other historic ownership exists.
GSS classification is supported and tested, but this slice adds no GSS producer:
the real Scheduled producer still notifies only Student and assigned Counselor.
No identity role alone grants access or source facts.

Each future source owner must define its own content-free eligibility and bounded
fact projection. Notifications orchestrates those interfaces; it must not infer
source authorization or duplicate source facts in mutable notification metadata.

## Content tiers

| Tier | Foundation behavior | Future approval boundary |
| --- | --- | --- |
| A: operational detail | No source fields rendered | Explicit event/recipient approval for date/time, reference, Service, Counselor, mode or public event title |
| B: minimal notice | Existing generic wording; one approved Scheduled action | Minimal links in additional events only after source/recipient review |
| C: security | Existing purpose-specific rendering, no operational link | Never genericize OTP/reset/MFA secret flows |

Never add Counseling narratives, Evaluation answers, assessment scores/findings,
Referral reasons, private Guidance Messages, handoff information, E-Counseling
join credentials/media/transcripts, Good Moral OR/payment facts, session tokens,
passwords, OTPs or MFA secrets. Hostile source labels, names, stored Notification
copy and arbitrary URLs are ignored by the pilot. No remote resources, trackers,
link-click analytics or email-open tracking are introduced.

## Outcomes

`generic_event` preserves fixed copy for other catalog events. `invalid_target`,
`source_missing`, `recipient_denied`, `origin_missing` and `origin_invalid` produce
safe generic mail without a link. `source_stale` cancels the Scheduled delivery
using the existing status and `source_ineligible` code. `link_available` renders
one action. Unexpected resolution failures stop delivery using the established
terminal render-phase `template_error`, with a separate bounded stage diagnostic;
they do not silently expose data or enter SMTP retry.

An old but still scheduled Appointment may have been rescheduled/reassigned.
This pilot supplies no live schedule/provider facts and explicitly says to review
latest details; it never attributes a newer schedule to an older change event.
The stricter rich-email policy is deferred to [NOTIF-2](appointment-event-design.md).
