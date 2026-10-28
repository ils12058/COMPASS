# Accessibility and responsive evidence

The existing PageHeader/PageAction, Panel/GoodMoralSection, Input/Label, ContextHelp, ConsequentialActionDialog, RefreshFailureNotice and ActionStatus patterns are reused. There is no new styling system, modal framework, hand-rolled focus trap, payment step or navigation tab.

Inspection has a named alert dialog and request-specific description. Applicant/reference and saved receipt facts precede the explicit labeled checkbox; the attestation is unchecked on every opening. Confirm is disabled until affirmation and while review is stale/unconfirmed. Pending controls cannot be submitted twice or dismissed with Cancel/Escape. Focus moves to a recording-status target while controls are disabled, allowing the existing Radix trap to retain focus; completion moves focus to Done. Cancel returns focus to the Verify control; completion returns focus to the receipt heading when the opener no longer exists. Contextual Help uses its existing keyboard/focus behavior.

Status is always written in text, not conveyed by a green badge alone. Errors remain contextual alerts; success requires backend-confirmed evidence. Routine correction success uses ActionStatus. Pending inspection has a polite status announcement. Blocked refresh uses the shared persistent notice and read-only retry. No attestation is prechecked or remembered as a preference.

Browser checks exercise keyboard Space on the checkbox, Tab containment during confirmation/pending, Escape refusal during mutation, duplicate-action refusal, Cancel/Done focus, action labels and checked/disabled states. They are automated accessibility evidence, not a manual screen-reader certification.

Responsive fixtures include 320px mobile portrait, 768px tablet and 1440px desktop; 200% root text scaling at tablet; long applicant names, 96-character ORs and large synthetic amount displays. Fields wrap with min-width/word-breaking, actions wrap, and the dialog has bounded viewport height with its established scrolling. History remains a disclosure rather than a wide table. Screenshots and horizontal-overflow assertions were inspected. 200% text scaling is reported distinctly from native browser zoom or assistive-device testing.

All browser responses are local mocked contracts. Native print dialogs, physical paper/signature/dry seal, manual keyboard checks on real devices, real screen readers and institutional UAT remain GM-OR-4 release evidence. Existing PDF/print components are unmodified and covered by their own regression suite.
