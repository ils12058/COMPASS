# Additive migration and preservation

New migration:
[0002_program_policy_and_catalog_initialization.py](../../be/compass/organization/migrations/0002_program_policy_and_catalog_initialization.py).
It depends on Organization 0001, creates the receipt table and policy columns, installs the immutable
array-check function, backfills policy, and adds constraints. It is registered in
[canonical_migrations.json](../../be/compass/common/canonical_migrations.json). No baseline migration
or existing baseline hash is changed.

The migration embeds 38 exact `(Campus code, College code, Program code)` policy entries: 30
Bachelors configured 1–4, five Masters pending and three Doctoral pending. It uses historical models
and the schema editor's database alias. No mutable canonical/policy module or model.save is imported.
Only the three new fields are updated, preserving updated_at/created_at as well as UUID/name/code,
active flags, parents and consumer records.

| Existing state | Backfill |
|---|---|
| Exact identity including renamed/inactive row | Frozen policy only; current name/status retained |
| Additional or changed-code/parent identity | NULL / PENDING_POLICY / NULL; no name inference |
| Missing baseline row | No creation or top-up |
| Fresh empty DB | Schema/backfill leaves catalog empty; explicit seed later supplies policy |

The migration does not write an initialization receipt or runtime Audit. Explicit seed/adoption owns
that evidence after migration. It neither deactivates extra rows nor initializes deployed data.

`RunPython(backfill_program_policy)` is intentionally irreversible. Dropping/reversing adopted policy
is not a compatible operational rollback. Keep the additive schema and use a compatible image or
roll forward. Failed forward migration remains atomic: a synthetic injected failure after actual
backfill rolls back new columns and data, leaves the migration unapplied, and succeeds on retry.

The populated-upgrade test creates a separate disposable UTF8 PostgreSQL database at Organization
0001, with 38 baseline identities, a removed offering, renamed/inactive entries, additional active
and inactive rows and changed identities (39 total Program rows before/after). It compares every
original field of Campus, College, Program, affiliation, responsibility, supervision, submitted
Inventory, issued Good Moral and Tracer rows. The historical migration fixture uses ciphertext
preservation sentinels and does not claim decryption/render validity; separate normal-domain tests
exercise real encrypted records and issued rendering/PDF compatibility.

Every remaining exact match receives the frozen policy; unknowns stay unresolved; no receipt is
created. Repeated migrate is a no-op. The reverse attempt is rejected. Fresh migration/seed and
raw PostgreSQL constraint tests provide separate evidence. See [validation](validation.md) for the
final executed selection and limitations; no deployed population or live migration is claimed.
