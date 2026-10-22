# Follow-ups and remaining verification

- **Manual assistive-technology review:** VoiceOver/Safari and another supported screen reader should verify status announcements, form labels, error-summary navigation, confirmation dialogs, focus return, native selector operation, and read-only states. Automated DOM/browser assertions do not verify spoken output.
- **Actual browser zoom and physical devices:** The Inventory matrix uses 100%/200% root text sizes, not actual browser zoom. Verify browser zoom and physical iOS/Android devices, including touch comfort, rotation, and scrolling.
- **Institutional UAT:** GCO and Student task review remains necessary for Intake uncertainty messages, saved-answer comparison and deliberate confirmation; Inventory section navigation at enlarged text; and Feedback/CSM recovery states. Proposal #15 remains experimental pending institutional acceptance.
- **Backend integration testing:** No backend code changed. Synthetic fixtures do not prove deployed database locking, authorization, replica freshness, Redis reservation/replay behavior, or races between independent requests. Test those against an approved non-production environment before institutional reliance.
- **Exact-body provenance:** Feedback opportunity submitted flags do not identify the request body that created the submission. The UI therefore reports the opportunity as already submitted without attributing it to the preserved request body.
- **Hosted CI:** Local validation is distinct from hosted CI. This work did not alter CI branch filters, dispatch deployment workflows, or claim a hosted run.

No backend release, migration, deployment, protected-branch change, or policy approval is part of this PR.
