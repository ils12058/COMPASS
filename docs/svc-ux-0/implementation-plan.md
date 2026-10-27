# Recommended implementation slices

These are **PROPOSED**, not authorization to activate, deploy, change policy or widen access. Order the slices so Student discovery can reuse existing APIs and staff access is corrected without new domain ownership. All work must rebase/reverify the current integration branch, generated OpenAPI contract and existing tests.

## SVC-UX-1 — Student discovery and pathway clarity

- Design a lightweight Service-centered entry that links to existing flexible, fixed and group flows and maintains meaningful Service context where the contract permits. Keep direct pathway and history routes, lifecycle eligibility, and domain-specific actions. Start with existing catalog/booking/discovery APIs; assess pagination, query volume, privacy and exact eligibility before adding any projection.
- Use distinct labels and truthful states: enabled vs real times/seats; show delivery and applicable Inventory requirement without asserting a group prerequisite. Provide route back to browsing and to each history, including event detail and success states.
- Preserve flexible idempotency, recheck and current-Student gate. For fixed/group, design a read-after-uncertainty path supported by existing authorized endpoints; no automatic retry and no claim that server replay exists. A retry must not create a duplicate. Continue to honor server 403/404/409 and scoped state.
- **Acceptance:** synthetic browser scenarios cover multi-path, single-path and no-offering Services; empty vs error; current and non-current Students; no/changed Inventory; stale and simultaneously taken slots, closed/full/conflicting event, successful confirmation and history/deep links; uncertain responses reconcile or remain explicitly unknown. Generated-client contract unchanged unless a separately justified contract gap is approved.

## SVC-UX-2 — Service administration and scheduled offerings

- Present three pathway configurations as peers; label flexible-only settings and the fixed-Inventory constraint accurately; distinguish Service activation, pathway enablement, and published offerings. Preserve mode, coverage, duration, cutoff, required Counseling, and E-Counseling readiness meaning.
- Provide a discoverable scoped fixed-slot management entry for Counselors and supervised GSS using existing operations and server scope, without `services.manage` as a prerequisite. Retain separate Group Sessions workspace and facilitate contextual links only when authorized. Reuse components, not a second administrative module or scheduling engine.
- Preserve MFA, consequence review and explicit confirmation, transactional semantics, current provider qualification and historic commitments.
- **Acceptance:** default Counselor and supervised GSS can reach only their authorized fixed-slot scope; inactive/unsupervised/revoked and IT-only actors cannot gain operations. Test all/selected coverage, group facilitator vs provider, inactive/enabled states, publication, withdrawal and configuration changes with existing commitments and failed/reviewed updates. Verify applicable recent-MFA behavior end-to-end before choosing any continuation pattern.

## SVC-UX-3 — Cross-role consistency and final validation

- Verify Home, sidebar, search, back navigation, notifications and direct history across roles; accessibility at small widths, keyboard, native zoom and screen readers; response loss, stale state and conflicts across all three domains. Verify service-state and E-Counseling copy with GCO.
- **Acceptance:** focused backend concurrency/authorization/history tests, generated contract checks, frontend unit tests and synthetic Chromium/WebKit regressions pass; real authenticated integration and manual accessibility are reported separately. Record a role/pathway matrix and unresolved failures, with no unsupported claim of UAT or release readiness.

**PROPOSED:** no standalone backend foundation slice: existing endpoints cover the core bookings and scoped operations. A future read model or backend policy change needs a concrete proven gap, separately reviewed contract, authorization and tests. See [open decisions](open-decisions.md).
