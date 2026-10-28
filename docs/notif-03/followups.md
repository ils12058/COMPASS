# Remaining decisions and NOTIF-04

## Institutional approval

Approve the complete central candidate bundle before live selection. Exact fields,
recipient scope, external mailbox/privacy expectations, stale-message behavior and
final copy need GCO/UCN sign-off. No earlier proposal or Appointment-only approval
implicitly covers additional domains. No live activation is included.

Possible later fields need their own reviewed version: safely classified Group
Session titles/public venue, facilitator context, Call Slip reporting time and any
staff identifier. Version 1 omits them. Registrar dry-seal instructions require
confirmed guidance; the existing Good Moral status does not track physical handoff
or sealing. Receipt integrity/payment integration remains a separate proposal.

## NOTIF-04 cross-channel work

Coordinate the same source events through email, Notification Center, browser Push,
authenticated record routes, login/MFA and revoked-access states on desktop/mobile.
Preserve in-app history where a delayed external message suppresses. Current tests
cover actual self endpoints, redirect validation, Push/realtime regression and
bounded transport races; they do not claim a full new cross-channel browser/UAT
campaign. No Notification Center or Push enrichment was implemented here.

## Manual environment/client validation

An authorized future staging SMTP smoke must use synthetic recipients, confirm
worker version/profile/origin consistency and exercise retry/cancel/legacy queues.
Gmail/Outlook, spam filtering, delivery/inbox behavior and assistive-technology
testing remain manual follow-ups. Local browser email layout and locmem transport
are implementation evidence only. No real Student records or emails were used.

## Provenance limits

Group Session registration does not snapshot its initial schedule; use explicitly
current context. Reschedule has a schedule revision but no previous interval;
show only the verified updated schedule. Legacy general revisions remain minimal.
Session-cancel participant proof uses the producer's exact cancellation timestamp;
incomplete historic participant proof receives no new details/link.

Good Moral has no canonical reference code; do not invent one or a payment/seal
stage. Call Slip LEGACY_UNKNOWN is not LIVE, though its existing void-notification
intent remains valid. Unsupported/out-of-band source rewrites cannot be certified
as immutable history. New snapshots/history models would need a precise fact gap,
source owner, privacy/retention and migration review. None is needed for this slice.
SMTP remains at-least-once and the final read/transport gap remains documented.
