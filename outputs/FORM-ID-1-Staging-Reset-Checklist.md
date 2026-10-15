# FORM-ID-1 owner-authorized staging release checklist

This checklist is preparation only. No staging reset, deployment, production migration, or merge was executed by FORM-ID-1.

- [ ] Resolve the inherited Graduate Tracer seeder/classification blocker and inherited CI formatting/shard coverage failures. Require passing validation on the final release SHA.
- [ ] Complete DOC-TPL-1 review of the documented F2 duplicate-copy/spelling and Word pagination differences. Retain approved wording and the confirmed F2 Revision 2.
- [ ] Obtain the owner's explicit approval for the specific staging reset and deployment. Confirm the environment and data-loss scope; take and verify required backups and recovery material.
- [ ] Confirm real institutional records will not be deleted under a demo reset. Confirm the reset targets staging, never production.
- [ ] Preserve required confidential-content encryption keyrings, storage configuration, identity settings and institutional artifacts. Do not generate replacement keys for existing encrypted records.
- [ ] Stop writes during the authorized cutover and follow the separately approved database reset procedure. This change supplies no destructive reset command.
- [ ] Deploy the reviewed backend and corresponding frontend contract, including Exit Interview migration `0005_saved_form_revision`.
- [ ] Run `python manage.py migrate` against the explicitly confirmed target.
- [ ] Run `python manage.py sync_identity_policy`, then `sync_canonical_services`, `sync_institutional_forms`, and `sync_organization_catalog` as appropriate, then `check`.
- [ ] Repeat `sync_institutional_forms`; require no changes. Verify all eight families have exactly one active exact supported revision, seven approved UCN identities plus unchanged CNSC F14 Revision 0.
- [ ] If approved for synthetic staging, explicitly configure demo seeding and run `seed_demo_staging`; require success and verify an idempotent repeat. Keep credentials out of reports.
- [ ] Verify F2 Revision 2 / schema 1; F3/F4/F5/F6/F7 Revision 1 / schema 1; F9 Revision 1 / schema 2. Check Institutional Forms displays these identities as ready.
- [ ] Create Inventory, Referral, direct/referral-derived Call Slip, both Good Moral variants, scheduled/direct Routine Interview, and Exit Interview using authorized test accounts.
- [ ] Inspect generated F2/F3/F4/F5/F6/F9 PDFs for saved identity, complete approved questions/fields, signatures, receipts and actual page numbers. F7 must not acquire a PDF workflow.
- [ ] Confirm UCN F9 has 23 College feedback items, rejects Program Chair content, preserves numeric zero and identity through reopen/correction/resubmission. Legacy null F9 retains 26 items and no fabricated UCN label.
- [ ] Confirm legacy CNSC PDFs use saved codes and revisions; legacy null F7 stays null; unknown revisions fail safely.
- [ ] Submit Customer Feedback with optional respondent identity and confirm CNSC F14 remains active. Confirm no UCN F14, F1 workflow, or F8 workflow exists.
- [ ] Verify Student, assigned Counselor, Head/designated reviewer and unauthorized-role boundaries using the existing permissions model; confirm confidential answers never appear in logs, audit metadata or unrelated responses.
- [ ] Re-enable writes only after smoke checks pass; record the final deployed SHA and release evidence. Keep a recovery decision available if any bootstrap or document check fails.
