# Actor, resource and time validation

Result: implemented boundaries PASS under isolated synthetic policies. Production disclosure is BLOCKED because all genuine providers and institutional approvals are absent. UUIDs, capability overrides, ACTIVE metadata, client state and evidence-shaped strings independently establish no authority.

## Actor matrix

`test_continuity.py`, `test_continuity_access.py`, `test_handoff.py`, their real PostgreSQL concurrency suites, and `test_cont4_final_security.py` execute the following boundaries. Exact parametrized test IDs are retained in validation evidence.

| Actor/relationship | Expected and verified result | Principal test families |
| --- | --- | --- |
| Original active author | Ordinary source/Summary authoring survives; Handoff drafts author-only; Grant alone adds no historical source ownership | Summary/Routine ordinary suites; Handoff planned lifecycle; CONT-4 Summary integration |
| Exact receiving Counselor | Effective approved exact selected source; submitted Handoff only; no ordinary source edit or Summary bypass | selected projection success; Handoff planned lifecycle; selected ordinary-read/write denial |
| Unrelated Counselor | Concealed body denial before decrypt | only-exact-receiver; denied Handoff relationship |
| Cross-College receiver | Exact approved policy/Student scope can permit access despite receiver responsibility in another College | cross-College/legitimate-Head-receiver case |
| Head with no participant relationship | No general Summary/Evaluation/Handoff content right | only-exact-receiver; denied Handoff relationship; CONT-4 Summary integration |
| Head as requester | Requires separate legitimate approver; own request does not self-authorize | self-approval denial; unplanned independent backup |
| Head as receiver | Can receive only as exact qualified receiver; cannot approve own receipt | cross-College/legitimate-Head-receiver; self-approval denial |
| Head as approver only | Structural metadata only, no draft existence/body decryption | metadata no-decrypt; structural selection; browser approver-never-fetches-body |
| Inactive Counselor | Current read/mutation denies, including stale actor objects | current-authority invalidations; inactive/stale-user; real deactivate race |
| Former Counselor (role changed) | No professional path despite retained historical UUID/capabilities | role invalidation, supported role-change race |
| Original author departed | Historical authorship retained; independently valid receiver may still read submitted source/Handoff | original-departure tests |
| Revoked capability/dependency | Direct API/service denies before decrypt; missing-row REVOKE phantom fenced | current-authority; authority-relation/missing-override concurrency |
| Expired override | Exact backend time removes authority, including after wait/preparation | current-authority; override expiry during selection/approval |
| GSS with overrides | Unsupported canonical role; supervision grants no professional authority | unsupported-role families |
| IT Administrator with overrides | Unsupported canonical role; no content/approval bypass | unsupported-role families |
| Student | Own published Summary only; draft/other Student/selected Evaluation/Handoff denied | Summary ordinary/encryption; CONT-4 publication never converts Handoff audience |
| Institutional Officer | Unsupported role despite overrides | unsupported-role families |
| Unauthorized Acting Head | Capability/expiry/reason alone lacks designation and verified delegation; denied | current Head/no Acting override; unverified Acting Head with expiring override |
| Synthetic independent approver | Current designated policy-named qualified second Head can approve a legitimate case | unplanned independent backup |
| Requester or receiver attempting self-approval | Denied even if also Head | self-approval tests |

## Exact source and time matrix

`test_continuity_access` covers correct Student/Grant/receiver; wrong Student; guessed existing Grant/source; unselected source; wrong kind/projection; changed revision; invalidated finalized Evaluation; changed source author, Encounter linkage, Appointment relationship and Student affiliation; missing/changed/expired disclosure/operational policy; changed exact field manifest; revoked/expired/scheduled Grant; later-created source; source selected under another authority; and current session revocation/rotation/expiry. Negative cases spy on decryptors. Snapshots/revisions are not silently refreshed. `test_valid_second_grant_cannot_accept_first_grant_ciphertext` adds two structurally valid independent Grant/document identities rather than only malformed metadata.

Every selected read independently locks and validates the source-owned lifecycle/revision. Encounter emits exactly `id, started_at, ended_at, entry_mode, delivery_mode, counselor_id`. Routine returns only policy-approved keys from the nine pinned Evaluation names. Unapproved field omitted, approved null rating, approved empty text and disclosed nonempty value remain distinct. Intake ciphertext is deferred; `test_only_evaluation_ciphertext_is_loaded_and_intake_never_decrypted` exercises corrupt Intake without decryption. No hidden ordinary-detail call is needed by the receiver UI.

Excluded from the enum/adapters: Student Summary, Intake, Referrals, Follow-Ups, full Inventory/Support, Assessments, recordings/transcripts, Guidance Messages, credentials and bulk exports. Existing unrelated domain rights remain independently evaluated. A Grant cannot create an Appointment provider relationship, Context anchor, Follow-Up assignment/manage authority, or general Student history right. These are checked by enum rejection, selected ordinary-route denial, source inspection and the canonical API inventory; this is not a claim that every unrelated domain endpoint received a new live attack test.

## Independent audiences

Student Summary author GET/PUT/publish and Student own-published APIs remain separate. Drafts deny Student/other Counselors; publication is immutable/idempotent. Removed ordinary legacy and Context summary-history URLs stay absent. Frozen old codec/migrations retain historical names only; no active binding alias/fallback survives. CONT-4 directly establishes that successful selected Evaluation/Handoff reads still cannot open the original author's Summary, and Student Summary publication cannot expose the Handoff.

Handoff is one optional independent confidential resource per Grant. Author-only versioned drafts; immutable submission; receiver submitted-body access only during effective coverage; both author and receiver deny new body reads after expiry. Metadata omits plaintext; receiver/approver cannot see draft existence. Exact Grant/Student/author/recipient/document and ciphertext swaps deny; historical source ownership never changes. Missing rings fail body operations safely.

## Read, Audit and notifications

Selected reads and Handoff operations require an outermost durable READ COMMITTED transaction. Shared policy fence → sorted User locks → exact Grant/Scope NOWAIT → fixed authority SHARE NOWAIT → current HTTP session NOWAIT → exact source/dependencies or Handoff NOWAIT. Recheck before decrypt, after preparation and after synchronous content-free Audit. The final successful check is authorization's linearization point; transaction commit precedes body return. Audit failure/late expiry rolls back the event and prepared body/mutation. New concurrent Handoff tests prove one failing read cannot emit another read's success or escape its rollback.

Audit actions: `counseling.continuity.requested/approved/declined/cancelled/revoked/selection_read/source_read`; `counseling.handoff.draft_created/draft_updated/submitted/read`. Actor/target/version/opaque references and bounded UUID metadata are intentional; no score, narrative, Intake, Handoff body, ciphertext, key or credential is recorded. A success event proves authorized server preparation/commit, not delivery, reading or comprehension. At a 15-second active protected-query interval, one open body can create about four read events/minute plus initial/focus/reconnect reads; additional open bodies add reads. Production event volume and monitoring are NOT VALIDATED (D13).

Continuity/Handoff Notification producers remain absent. Positive operations create no in-app/EmailDelivery/PushDelivery intent; no protected body enters generic realtime/tab hints. Student Summary publication notifications are separately tested and functional. Stale deep links reauthorize. New recipients/channels/currentness and Student transparency remain D08/D15 blockers.

Locks cover supported ordinary PostgreSQL DML, including missing authority-row insertion. They do not prove synchronization for arbitrary privileged schema/data rewrites, unfenced external policy providers, mixed runtime versions, or stale allow caches. Earlier committed information and screenshots cannot be recalled.
