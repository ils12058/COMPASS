# Follow-ups and limits

- **Manual accessibility review:** VoiceOver/Safari and NVDA, actual 200% browser zoom, physical
  mobile devices and touch comfort remain to be verified. Automated root-font enlargement is
  distinct from browser zoom. WebKit's automation runner defaults to macOS form-control-only Tab;
  full link traversal with Safari's Full Keyboard Access must be checked manually. The suites check
  DOM order, native focusability and focus indicators there; Chromium exercises sequential Tab.
- **Institutional task review:** GCO/Student UAT should assess whether the four service links match
  actual return visits and whether five attention rows remain a useful preview. No questionnaire,
  record eligibility or service availability should be inferred from this layout. Proposal #15
  remains experimental pending review and acceptance.
- **Read-model limits:** Overview supplies exact counts, not an Appointment agenda or certificate
  readiness feed. Student Actions supplies a paginated preview and `has_next`, not a total or
  progress score. No additional backend read model was justified or implemented. Broad service
  discovery still belongs to authorized navigation and domain workspaces; the management Services
  workspace cannot serve as a Student catalog merely because catalog reads exist.
- **Separate role-adaptive slices:** Counselor/Head and GSS work density, professional landing
  information architecture and contextual navigation can be evaluated independently after this
  Student slice is reviewed. Their queues, metrics and email status are intentionally retained.
- **Known unrelated Inventory reflow:** PR #304 recorded a 1,223px document at 1024px/200% root text
  beside the expanded dock, with the shell itself fitting its 512px region. This is Inventory-owned
  content work and remains outside Home. The shell regression suite retains this known exception.
- **Separate correctness work:** Routine Intake uncertain-submission canonical reconciliation and
  Feedback generic HTTP-error uncertainty recovery remain as documented in the form consolidation.
  Neither is implemented or reclassified as a visual change here.
- **Integration validation:** Local synthetic tests do not execute real database authorization,
  encryption, race handling or provider behavior. Backend behavior is unchanged and was inspected,
  not reimplemented. Hosted CI filters currently exclude integration-targeted PRs; any CI coverage
  change needs its own review. No workflow was dispatched to work around that exclusion.

No additional independently actionable correctness defect was demonstrated by this Home slice.
No follow-up authorizes a merge, deployment, new permission or institutional policy change.
