# FAC-1 Faculty institutional identity foundation

See [verified preflight and ownership](preflight.md),
[FAC-2 contract and unresolved policies](fac-2-contract.md), and
[validation evidence](validation.md).

`FACULTY` is a canonical single primary role with an empty capability baseline
and runtime ceiling. Generic grants, inherited designations and retained
overrides cannot give Faculty operational capabilities in this slice. Managed and
low-level GRANT writes reject Faculty; existing override rows remain inspectable
and removable. Other roles' defaults and dependency graphs are unchanged. Future
Faculty services must explicitly revise this ceiling alongside narrow authority.

`organization.FacultyAffiliation` records one nullable home College FK, a monotonic
resource version, institutionally assigned actor/time and assignment basis. The
College/Campus UUIDs come from the database-owned catalog. Missing/cleared homes
grant no services. Deactivation retains the reference; reactivation rejects
inactive ancestry. Leaving Faculty clears the current home with an Audit event;
returning to Faculty requires deliberate reassignment. Cleared rows retain their
version to prevent a stale client from overwriting a later assignment. Historical
College UUIDs, assignment actor/time and basis survive in synchronous Audit events.

Account managers provision Faculty through existing create/role/lifecycle flows
and a dedicated affiliation form. Single creation accepts optional
`faculty_college_id`; other primary roles reject a non-null value. The versioned
assignment endpoint requires `accounts.manage`, current institutional authority,
recent MFA, CSRF, an explicit expected version, a basis and a separate target.
It accepts no Campus override: ancestry derives from the selected College. Catalog
retirement and account/CSV writes share the existing gate before user locks; active
Faculty references block Campus/College retirement. No Program relationship exists.

The CSV schema adds only optional `faculty_college_id`. Blank is explicitly
unassigned. A nonblank value is accepted only for Faculty and must be an active
catalog UUID beneath an active Campus. Preview shows the UUID; the import page
provides active reference choices. Existing accounts SKIP only when normalized
identity, active status, primary role and Faculty home match exactly; a missing or
different home is a CONFLICT, never an update. All rows are revalidated at commit
and the existing transaction rolls back the complete import on conflict. No other
organizational or academic column is accepted. Preview is advisory; commit checks
the uploaded bytes and current database again, without auto-replaying changes.

Faculty Home states that digital Referrals are unavailable and shows the current
institutional home or “Not assigned.” Only own-account and Notification routes
remain accessible. Direct operational routes are blocked before their components
mount, and Faculty never receives Student self-service, GCO queues or IT controls.
The session and own Profile expose read-only affiliation. Existing opaque cookie,
email/password access, MFA, CSRF and cache-ownership architecture remain in use.

Installation requires the normal additive `organization.0004_facultyaffiliation`
migration followed by the existing explicit `sync_identity_policy` command.
There is no automatic Faculty backfill, account conversion, catalog reconciliation,
activation, deployment or production/staging data mutation in this work. The
cooperative catalog gate still does not fence old binaries or unrestricted SQL.
