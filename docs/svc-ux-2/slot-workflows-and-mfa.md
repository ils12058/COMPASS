# Slot workflows and MFA

The existing slot panel remains the single implementation for listing, creating, publishing,
unpublishing, linking, and withdrawing slots. Withdrawal preserves slot provenance and booked
Appointment history.

Create, update, and withdrawal continue to use the existing protected API operations. When the
backend returns `recent_mfa_required` or `mfa_setup_required`, the shared `StepUpDialog` is used.
After verification the slot and provider queries are refreshed; the original mutation is not
replayed. Staff must review the current target and explicitly submit again.

Backend conflict, qualification, supervision, inactivity, and booking checks remain authoritative.
An uncertain network response is not converted into a success claim by the client.

