# Future deployment prerequisites — no deployment performed

This PR is implementation and synthetic validation only. No DigitalOcean/Vercel
configuration, protected branch, SMTP provider, recipient list or live environment
was changed. Neither workflow dispatch nor automatic merge is authorized here.

## Required before activating rich external mail

1. GCO/UCN approves the exact `operational_v1` Student/current-Counselor field bundle,
   including Service names in external mail, schedule, current provider name for
   Students, recipient scope, terminal mail and retention/mailbox expectations.
   Proposal #5 describes direction and is not this approval.
2. The approved environment uses a validated HTTPS `COMPASS_PORTAL_ORIGIN`, with
   existing login/MFA/record authorization independently verified. No meeting URL
   or token can replace that origin.
3. An authorized operator deliberately sets the backend/worker configuration to
   `APPOINTMENT_EMAIL_DISCLOSURE_POLICY=operational_v1`. Absent, invalid or unknown
   values stay `minimal`. No frontend flag or per-user preference activates it.
4. All delivery workers run the same reviewed backend version and policy/origin;
   restart/rollout requirements follow normal environment procedures. Old workers
   continue generic rendering and cannot supply the new experience consistently.
5. Review queue age/source quality and cancelled-delivery diagnostics before an
   approved staged rollout. Existing queued events are projected at delivery;
   unchanged trustworthy ones can enrich after activation, legacy ones fall back,
   and obsolete rich events cancel. No historical sources are rewritten.

## Compatibility and future staged validation

No database migration, API regeneration, frontend rollout, new queue or task name
is required. Existing Notification, change-event, occurrence and EmailDelivery
records are reused. Generic event-code previews and default production copy stay
compatible. The merged NOTIF-01 frontend handles the same authenticated route.

After separate deployment authorization, first deploy with `minimal`; run local/
approved synthetic previews and origin checks. Then use only approved synthetic
test accounts and safe SMTP recipients in staging to verify HTML/text, policy,
source-currentness, MFA/authorization, all seven events and revoked/former cases.
Activate the approved version only after institutional and operator sign-off.
Inspect bounded outcomes without logging bodies/addresses; confirm actual Gmail/
Outlook rendering separately. These are future prerequisites, not executed steps.

## Downgrade and rollback

Set the single policy back to `minimal` through the authorized configuration
procedure and restart workers consistently. Pending messages return to existing
generic behavior and authorized Scheduled pilot links. A rich plan already
rendered before a policy change fails final comparison and cancels before send.
Already accepted external mail cannot be recalled. Cancelled deliveries remain
cancelled; rollback does not requeue obsolete events or resend historical notices.
Any deliberate recovery/reissue must use separately reviewed existing operations.

Code rollback needs no schema reversal and old workers can read unchanged rows.
SMTP acceptance remains at-least-once; SENT is not proof of reading or inbox receipt.
