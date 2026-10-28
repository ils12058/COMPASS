# Uncertain outcomes and recovery

| Path | Existing recovery contract | Evidence / boundary |
|---|---|---|
| Flexible Appointment | Reuse the same idempotency key for the same intent; a changed intent must not replay the old key. | Appointment backend/recovery tests and synthetic `svc-ux-1`/copy browser cases |
| Fixed slot | A network/unreadable/5xx result stays unconfirmed. Do not resubmit automatically or infer booking ownership from a missing slot; check My Appointments. | `bookingResultIsUncertain`, fixed-slot panel, SVC-UX-1 browser scenarios |
| Group registration | After ambiguity, query the authorized exact current-Student registration state. An active exact registration can confirm; absent/unreadable state stays unresolved. | Group Session recovery browser scenarios and backend registration tests |
| Confirmed write, failed refresh | Preserve confirmed success and report refresh failure separately; expose read-only refresh. | Synthetic SVC-UX-1 recovery scenarios |

The real fixed-slot browser success test confirms the normal transaction only. It does not induce response loss. No replay contract was added for fixed slots or Group Sessions, and no new idempotency mechanism was introduced.
