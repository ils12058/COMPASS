# ADR-119: Remove the provisional policy layer

- Status: Accepted owner decision; implementation does not authorize live operations.
- Date: 2026-11-10
- Supersedes the policy activation, provenance and release conditions in the linked historical feature documents.

## Decision

Remove policy objects, versions, evidence and authority references, validity windows, digests,
fixed activation audit events, stored policy columns and policy-unconfirmed error paths from case
coverage, Counselor Handoff, case-coordination messages, Faculty Referrals and Good Moral fees.
These are ordinary COMPASS rules. Future rule changes require a code change.

## Rules and integrity preserved

`compass/counseling/continuity_rules.py` owns live actor, office, Head and College membership,
independent approval, distinct active receiving Counselor, all reason categories, the 30-day
duration and 14-day advance limits, placement checks and overlap rejection across receivers.
Selected records remain Encounters and finalized Evaluations; Evaluation disclosure is limited to
`academic_adjustment_rating` and `recommendations`. Receiving Counselors read only selected records
while coverage is ACTIVE. Completed approvals survive Head turnover. Original Counselors author
Handoffs, intended recipients read them, and the separate Handoff keyring remains. Case coordination
stays between the grant's Counselors with purpose `CASE_COORDINATION` during active coverage.

`compass/referrals/faculty_rules.py` keeps active Faculty, Students in active Colleges on active
campuses, 300-second signed confirmations, and lookup limits of 10 per actor and 30 per IP per
300 seconds. Active Counselors and Guidance Office Assistants acknowledge and close; Faculty see
only their own submissions and received notices. Capability grants, dependencies and the Faculty
ceiling do not change.

`compass/good_moral/fees.py` fixes both F4 and F6 at PHP 80.00. Verification stores expected amount
and currency; issuance compares those terms. Receipt dates, actual amount, binding, fingerprints,
inspection timestamps and revisions remain enforced.

Real user-action audit names, content-free metadata, selected-scope snapshots (without policy
fields), source revisions, optimistic versions, row locks and Referral immutability triggers remain.
The API drops grant/selected-read policy fields, coverage policy validity and Good Moral fee status.
The frontend follows that contract. Seed and verification use normal services without activation
records; Privacy Notices end with Your rights.

## Baseline and delivery

Edit existing counseling `0001`, referrals `0001`/`0002` and good_moral `0001`/`0002` release baseline
files in place. Recompute both canonical and deployment SHA-256 manifests. Add no removal migration.
Migration names are unchanged, so a routine deployment cannot detect or apply these schema edits.
**Delivery to staging is reset only**, using the owner's separately approved reset procedure after
review and green CI on the exact promoted head. This PR authorizes no merge, staging push, workflow
dispatch, deployment, reset or credential issuance. Existing historical documents remain history;
the dated notes point here for current rules.
