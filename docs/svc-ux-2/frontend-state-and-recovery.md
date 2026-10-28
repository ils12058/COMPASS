# Frontend state and recovery

The new route keeps Service selection in local component state and uses bounded TanStack Query
pages. Slot mutations invalidate the existing Service slot query; MFA completion explicitly
refetches slots and provider candidates before another confirmation.

Errors remain visible as errors. Refresh failures do not become mutation success, and a missing
record on a paginated list is not treated as proof of withdrawal or deletion.

