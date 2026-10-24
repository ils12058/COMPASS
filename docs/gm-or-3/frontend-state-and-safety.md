# Frontend state, review identity and safety

Canonical authority is the unchanged `contracts/openapi.json`. Orval was generated before edits; source imports generated payloads/responses/operations/query keys. Generated clients are ignored and not hand-edited/committed. No backend contract or role/policy changes were needed.

## Inspection intent

`receipt-review.ts` stores a cloned saved operational response for presentation and an exact generated verification payload. Opening inspection freezes request ID/version, assignment, applicant/receipt facts, method and a cryptographically generated operation UUID. Reopening an unchanged intent retains the operation identity and always clears the checkbox. Different reviewed resource/revision requires a new explicit review. The client never transfers an attestation to replacement facts.

`use-receipt-inspection.ts` prevents duplicate submission with a synchronous ref plus pending state through mutation and reconciliation. Mutation retry is false. It consumes backend state; its comparison helpers determine whether a returned inspection belongs to the reviewed receipt, not whether a payment is valid. No receipt facts, attestation preference or operation ID enter localStorage/sessionStorage/URLs/telemetry.

A successful response is followed by canonical detail refresh. Current status must be backend VERIFIED on the exact assignment; own completed success additionally matches the committed verification UUID and has no invalidation timestamp. An old successful response followed by a newer invalidated/replaced receipt cannot succeed in the UI. Another actor's attestation is displayed as that actor's original reference/time rather than rewritten as the current user's inspection.

## Uncertain and stale outcomes

A network/5xx result never means automatic failure or success. Canonical GET may confirm an existing current inspection, reveal changed/terminal/unavailable state, or still leave the same receipt unconfirmed. The latter retains the original UUID and requires another initially unchecked review before a deliberate retry. No unsafe request is replayed automatically. A failed GET retains last-known facts with the shared RefreshFailureNotice and blocks consequential work; Check current request only performs a read.

Receipt conflicts, policy loss, a cutover pause, authority refusal and request lifecycle conflict close stale confirmation and refresh. Changed background versions invalidate the frozen review and disable its confirm action. Generated TanStack query cancellation owns overlapping refetch ordering (`cancelRefetch: true`); mutation responses are never optimistically written over newer canonical detail. No additional polling loop or WebSocket was added.

The affected detail, operational queue and Guidance work keys are invalidated on confirmed inspection. Detail invalidation does not launch a redundant active refetch before the explicit canonical read. Other application domains are untouched.

## Editors and account boundaries

The existing correction form keeps its draft mounted through transient detail-refresh failures. Busy protection now covers the complete save/refresh interval. Receipt conflict/uncertainty preserves input, displays latest saved values separately and requires deliberate review. A failed refresh prevents Save. Closing a dirty editor retains the existing discard confirmation. Inspection is unavailable while the editor is open; other mutations are unavailable during inspection/recovery.

The detail's local state is keyed to request, account, authenticated session and relevant Good Moral authority. A changed account/session/authority scope cannot inherit an open personal attestation. Inspection and correction ignore late asynchronous outcomes after unmount. The existing global QueryClient account-ownership fence removes the old account's protected queries and rejects old mutation outcomes; its six tests were rerun. Same-owner routine record refresh does not key/reset the editor draft. Losing account/authority scope deliberately removes private local state.

Existing issue tokens remain pinned; the issuance confirmation also freezes displayed facts and blocks stale/failed-refresh submission. The backend still enforces actual authority, current revision, fee decision, idempotency, Student eligibility and all transaction invariants.
