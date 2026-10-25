# Cross-domain and historical compatibility

ORG-1 changes catalog authority/policy source, not institutional rules. StudentAffiliation,
CounselorResponsibility and StaffSupervision models/services and ownership remain intact. Existing
role-transition conflicts, dynamic GSS supervision, default Counselor resolution and Head fallback
are unchanged. Inactive College/Campus still fails routing before fallback. No assignment is silently
removed, reparented or copied. Catalog grants, SAR and confidential access are not introduced.

Inventory preserves actual integer 1–10 storage, known/unknown pending compatibility and configured
membership validation. New selection/submission still requires active Program/College/Campus;
unchanged inactive Program draft edits retain their existing behavior. Submission freezes current
course text, while the Program FK/API summary remains a live catalog reference. Existing reopening
restrictions stay. No old submission/year/course/timestamp is rewritten.

F4 new requests/corrections use persisted Bachelor policy and fixed supported Year 1–4 labels.
A noncanonical database Bachelor can submit Inventory and create F4 without seed registration;
a policy including Year 5 still cannot issue a new fifth-year F4. Current lifecycle, Inventory and
affiliation prerequisites, request idempotency, preparation, receipt checks and issuance rules remain.
Pending requests retain their established snapshot behavior; ORG-1 does not add policy revalidation
to issuance or change GM-OR activation, ledger or verification configuration.

F6 suggestions are current active database degree names, not an eligibility whitelist. Reported
historical degree text, graduation facts, current postgraduate reenrollment handling and certificate
snapshots remain. Issued certificates use saved form/template/issuer facts. The final relevant
regression includes actual F4/F6 PDF/render tests and GM-OR preservation tests where available;
see [validation](validation.md) for observed results rather than assuming they all ran.

Graduate Tracer still stores graduation College/Program FKs and displays live catalog labels.
Historical inactive reference semantics are not globally narrowed. Reports retain their historical
Inventory facts, current parent/name joins and current permitted scope; no effective-dated name
history is fabricated. Exit snapshots and Routine's optional linked Inventory context remain.
Counseling Context's mixed current-reference/history presentation and all confidentiality policies,
ownership and keys are unchanged.

Current-use selection is explicitly separate from reference reads. Shared active-chain helpers
serve Inventory and degree/persona selection. Generic Organization list/detail and existing historical
Tracer/report lookups remain inactive-inclusive as before; a future status editor must implement
transactional blockers, pending-work review and correct domain-specific history access.
