# Call Slip email contract

Source type `call_slip` and source UUID must match the CALL_SLIP target. Only the
actual Student with active Student identity, `call_slips.view_self` and successful
`get_my_call_slip` ownership qualifies. The capability check matches the existing
API boundary, which is separate from the service getter's role/ownership check.
The normal `/portal/call-slips/{id}` page/self endpoint remains authoritative,
including retained voided history. An unrelated recipient gets no details/link.

## Original notification intent

LIVE issuance is persisted when the existing producer uses `notify_student=True`.
HISTORICAL back-entry remains quiet through its entire lifecycle. LEGACY_UNKNOWN
does not establish LIVE provenance and cannot create a fresh issuance email.
Projection/retry never creates an issuance, Notification or replacement intent.
No Referral/issuance/deduplication workflow changes.

`call_slip.issued` requires LIVE and ACTIVE: no void or interview-completion marker.
A queued issuance that becomes voided/completed suppresses, using existing terminal
delivery cancellation rather than a pointless transport retry. A past reporting
time alone does not rewrite its stored lifecycle; the mail carries no reporting
time/attendance promise and directs the Student to the record.

`call_slip.voided` requires an actual void timestamp and existing
`void_notifies_student` eligibility. HISTORICAL remains suppressed. The domain's
existing rule permits LEGACY_UNKNOWN void notifications; these retain minimal
withdrawal copy and an authorized history link without asserting new LIVE proof.
LIVE voids may receive the approved fixed voided-status row. No void reason or
new reporting instruction appears. Private source details stay in COMPASS.

## Candidate version 1 fields

The only new field is a code-owned “Call Slip issued” or “Call Slip voided” status.
Report date/time is stored but deliberately excluded pending explicit institutional
field approval. All destination fields are also excluded because they can reveal
sensitive context. No Student/course identifiers, issuer names, Referral narrative,
Counseling/behavioral reasons, internal remarks or void reasons are projected.

HTML/text share the single trusted route and fixed action label. Generic event-code
previews remain supported. Source mode/lifecycle/void/completion markers and the
effective central profile/URL enter final comparison; excluded reporting/destination/
name edits do not arbitrarily cancel an unchanged minimal status message.

Missing legacy source references use original generic no-link rendering. Historical
or obsolete issuance sources cancel; valid legacy voids follow the explicit rule
above. Stored records remain compatible even though the old environment setting
does not. Source-specific email guards do not change Push or in-app lifecycle.
