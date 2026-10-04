# Retention and disposition deployment / restoration

This runbook accompanies ADR-072. Approval authorizes real irreversible live-data treatment. Use
synthetic fixtures and fake Daily clients when validating; do not test deletion against counseling
artifacts without an explicitly dedicated test provider account.

## Deployment

1. Deploy the same reviewed backend image to web, Celery worker and one Beat instance.
2. Run normal explicit migrations and `python manage.py sync_identity_policy`. Migrations create
   schema only: they never activate a rule, infer eligibility, anonymize or delete existing records.
3. Verify current OpenAPI, frontend Orval generation and normal readiness/worker diagnostics.
4. Restart worker and Beat. Check registration of `compass.privacy_governance.discover_retention`,
   `compass.privacy_governance.execute_disposition` and `compass.privacy_governance.recover_disposition`.
   Discovery runs every 300 seconds; approved-dispatch recovery every 60 seconds. No unapproved row
   may be queued by either schedule. Existing notification schedules remain intact.
5. Keep rules empty/inactive until the institution supplies adopted references, durations and
   effective dates. Never create an ACTIVE demo policy to make a demonstration look populated.
6. Confirm Daily is enabled/configured only in the intended environment. The executor uses the
   existing server-owned credential/timeout configuration and never exposes it to the DPO.

The DPO designation alone receives baseline retention view/manage/approve. Drafting and holds use
normal authorization; activation, retirement, approval and authorized retry use backend recent MFA.
Capability overrides are institutional exceptions, without underlying confidential-content grants.

## Review, dispatch and failure

Eligibility is discovered in bounded pages of 200 sources/cases per category. Large backlogs settle
over successive discovery passes. Summary counts are stored review cases, not a claim that every
record has been scanned instantly. Each approval freezes one source and exact rule revision.

Approval commits QUEUED before dispatch. A broker outage leaves that durable row for Beat recovery;
the user must not approve it again to force execution. PROCESSING uses a claim token. Three automatic
provider attempts use 60/120-second delays. Provider permanent failures are FAILED; uncertain
outcomes are RECONCILIATION_REQUIRED. Claims older than 15 minutes require review and reconciliation.
The recent-MFA retry path grants a bounded new attempt budget, up to three manual authorizations.

Holds can prevent unstarted/queued treatment. A hold revokes its old approval, and release does not
reapprove. An already PROCESSING provider operation cannot be stopped by a new hold or rule
retirement; the API returns a truthful conflict. Monitor the outcome before deciding the next step.

If Daily deletion succeeds but the local completion/audit transaction fails, the capture reference
and PROCESSING claim remain for reconciliation. A transcript `t_deleted` result can safely complete
a deliberate retry; uncertain recordings remain unresolved.

Do not clear source/provider evidence to "fix" a failed case. Confirm provider response/identity and
current source/rule state. Daily transcripts can reconcile `t_deleted`; recordings with a missing
response/artifact require provider investigation. Never interpret an arbitrary 404 as proof that
the correct media was erased. No raw provider payload, URL or token belongs in a case/audit note.

Customer-managed S3/OCI markers require deployment-owned external reconciliation. This workflow
cannot certify those objects erased, and leaves the case unresolved. Resolve storage disposition
under an approved infrastructure procedure; do not bypass the executor to manufacture COMPLETED.

## Live disposition and backups

Graduate Tracer treatment removes the identifiable live row and detailed children, preserving only
the documented analytical contribution under an independent UUID. Daily-owned recording/transcript
treatment verifies the supported provider deletion contract and minimizes the local artifact
reference. Neither claims erasure from exported files, devices, database snapshots or object backups.

Backup creation, expiry, object lifecycle and physical storage erasure remain deployment-controlled.
Expired backup copies follow the actual configured infrastructure retention schedule; this PR
introduces no backup-retention subsystem or invented infrastructure period.

## Historical restoration boundary

1. Keep a restored environment isolated from users, live provider calls, workers and Beat until
   reconciliation finishes. A historical snapshot may contain data already disposed in live state.
2. Obtain protected completed-disposition decisions from the authoritative environment/retained
   governance backup, including category, original source ID, approved rule revision and completion.
   Do not extract anonymous Graduate Tracer identifiers as a reverse identity map.
3. Compare those decisions with restored identifiable sources and provider references. Preserve
   minimized decision/audit evidence under the infrastructure recovery procedure.
4. Reapply the approved domain treatment or reconcile the provider's actual deletion. A restored
   transcript tombstone can confirm `t_deleted`; unresolved recording/provider state stays isolated
   until the infrastructure/provider owner verifies it. Never fabricate a new institutionally
   approved rule or silently reapprove data because it is old.
5. Validate anonymization, aggregate reporting, consent evidence, holds and unresolved cases. Only
   then enable authoritative user traffic and background schedules.

If completed decisions cannot be recovered, restoration cannot safely be declared authoritative.
Stop that restoration's release and obtain UCN/DPO/infrastructure disposition guidance. There is no
blanket database delete, AuditEvent bypass or automatic backup purge in this feature.
