# One versioned external disclosure selector

`COMPASS_EMAIL_DISCLOSURE_POLICY` is the sole general operational email disclosure
setting. `minimal` is the default; only the exact plain string `operational_v1`
enables the explicit candidate bundle. Empty/missing/unrecognized/differently
cased values and invalid runtime override types stay minimal. No frontend,
request argument, recipient preference or arbitrary list selects richer fields.
`COMPASS_PORTAL_ORIGIN` continues to control trusted routing, not disclosure.

## Exact candidate version 1 scope

| Family / recipient | Admitted fields | Explicit exclusions |
| --- | --- | --- |
| Appointment current owning Student | Existing reference, Service snapshot, current initial/exact event schedule, mode, current assigned/new Counselor name where permitted | Student identifiers, reasons, prior Counselor names, credentials |
| Appointment current assigned Counselor | Existing operational reference, Service snapshot, schedule and mode | Student identifiers/contact data and provider names |
| Appointment former Counselor | Existing minimal notice only, no protected link | All new source details |
| Group registration confirmed / owning Student | Fixed Group Session label, confirmed status, explicitly current date/time and mode | All source title/description/venue/facilitator/roster data |
| Group rescheduled / currently registered Student | Fixed label, rescheduled status, updated date/time and mode, only for exact schedule revision | Previous schedule, legacy general-version rich schedule, all free text |
| Group registration/session cancelled / proven Student participant | Fixed label and appropriate cancelled status | Upcoming date/time/mode or attendance promises |
| Good Moral assisted initiation / owning Student | Fixed request label and current Requested/Ready status | Receipt, applicant, academic or certificate details |
| Good Moral issued / owning Student | Fixed request label, issued status, verified local issuance date | OR number/date/amount, payment claims, academic standing, body, issuer name |
| Call Slip LIVE issued/voided / owning Student | Fixed status only | Reporting time/destination, identifiers, Referral/void reasons |
| Call Slip legacy unknown void / owning Student | Existing minimal copy and eligible link | New rich or LIVE provenance claim |

The code admits exactly 15 events across these four families: seven Appointment,
four Group Session, two Good Moral and two Call Slip. Each domain retains its own
fact/field vocabulary. New families or changed field/recipient boundaries require
a separately reviewed version; do not silently expand this profile later.
GSS receives no new rich bundle or recipients. Confidential Guidance, Counseling,
E-Counseling and all other non-admitted events remain generic/minimal. Security
messages keep their specialized contracts. Standard channel/preference rules stay
separate from this detail-disclosure decision.

## Approval boundary

This is a candidate bundle exercised with synthetic data, not a grant of GCO/UCN
approval. Approval of only Appointment fields, if obtained independently, cannot
authorize the expanded profile. An operator must obtain authorization for the
**complete table actually enabled by the central profile**, then deliberately
configure the new setting through a separately authorized operation. This PR
does not activate it. The new name and strict rejection prevent silently carrying
an old Appointment-only opt-in into the expanded set of domains.

## Strict retirement and cutover

`APPOINTMENT_EMAIL_DISCLOSURE_POLICY` is not declared or read for policy selection.
Its plain environment name or `APPOINTMENT_EMAIL_DISCLOSURE_POLICY_FILE` presence
causes a startup `ValueError` before ordinary settings parsing, including empty
values or coexistence with the new name. The fixed error instructs the operator
to replace it with `COMPASS_EMAIL_DISCLOSURE_POLICY`; it never prints the old
value/file content. No deprecated alias, fallback lookup, migration warning that
continues accepting it, dual precedence or hidden compatibility switch exists.

Current example configuration is `COMPASS_EMAIL_DISCLOSURE_POLICY=minimal`.
Remove both obsolete keys from backend and workers through an authorized future
configuration change. Pending stored sources are unchanged and resolve safely;
there is no queue/data migration. Historical NOTIF-02 docs retain original names
only under explicit supersession notices.

Downgrade the current binary by selecting `minimal` and restarting workers
consistently through normal authorized operations. Rich rows disappear while safe
links remain. A changed effective policy after rendering cancels before SMTP;
already cancelled deliveries are not revived. Removing rich approval cannot
recall an accepted email. See [deployment prerequisites](deployment-readiness.md).
