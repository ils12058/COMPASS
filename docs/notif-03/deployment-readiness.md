# Future approved cutover — no deployment performed

This integration PR does not authorize SSH, DigitalOcean/Vercel configuration,
workflow dispatch, real mail, protected-branch promotion or deployment. These are
future prerequisites only; no live environment was inspected or changed.

1. Obtain GCO/UCN authorization for the **complete** central `operational_v1` field/
   recipient bundle, including all four families. Prior Appointment-only approval
   cannot authorize Group Session, Good Moral or Call Slip additions.
2. Verify the approved HTTPS `COMPASS_PORTAL_ORIGIN` and normal login/MFA/record
   authorization for all supported destinations. Meeting URLs/tokens are excluded.
3. Through a separately authorized configuration operation, remove
   `APPOINTMENT_EMAIL_DISCLOSURE_POLICY` **and its `_FILE` form** from backend and
   every worker. Their presence, including empty, makes this binary fail startup.
   No alias, migration fallback or precedence exists. Configure the new
   `COMPASS_EMAIL_DISCLOSURE_POLICY=minimal` initially.
4. Roll out the reviewed binary and consistent origin/profile across workers using
   normal environment procedures. No migration, contract generation, new task or
   frontend release is required. Existing stored sources/deliveries remain readable.
5. Use approved synthetic accounts and safe SMTP recipients for an authorized
   staging smoke: all events, HTML/text, legacy/void/cancelled history, revoked
   access, supersession, retries and account/origin changes. Test real Gmail/
   Outlook/assistive technology separately; local previews do not prove these.
6. Only after full-bundle approval and successful approved validation, deliberately
   select `COMPASS_EMAIL_DISCLOSURE_POLICY=operational_v1` and restart workers
   consistently. Observe bounded cancellation/failure reasons without recording
   bodies, personal details or URLs. Review old queue/source quality first.

## Downgrade and code rollback

The current binary downgrades through the new selector's `minimal` value, not by
restoring the old setting. Rich rows disappear; safe authorized links remain.
A policy change after rendering cancels the old attempt before SMTP. Already
accepted mail cannot be revoked, and cancelled deliveries are not silently revived.
Any deliberate recovery/reissue requires separately reviewed existing operations.

An older NOTIF-02 binary expects its old configuration name. A future **code**
rollback therefore requires coordinated operator configuration for that older
binary; never restore the obsolete name while this new binary is running. There
is no schema reversal. Worker heterogeneity must not be mistaken for a consistent
profile rollout. None of these operations was executed here.
