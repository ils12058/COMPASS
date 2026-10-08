# ADR-091: UI information hierarchy, progressive disclosure, and product voice

## Status

Accepted for this frontend consolidation. Complements ADR-090 without changing collection ordering or domain behavior.

## Context

Operational details often placed record facts, state, actions, instructions and domain/implementation explanation in the same visual layer. This made technically accurate workspaces difficult to scan. Existing Radix Dialog, AlertDialog and Dropdown Menu behavior provided accessible interaction infrastructure, but there was no grouped contextual Help or shared named compact action pattern.

## Decision

1. Primary UI shows identity, content, current state, required next action and relevant warnings. Action consequences appear in confirmation/review or beside a consequential setting. Longer conceptual/domain explanations move to grouped contextual Help.
2. Use one page-level `ContextHelp` on complex workspaces. Optional section Help is exceptional; fields use concise input constraints, not repeated question-mark controls. Help supports headings, grouped sections and links using the established Dialog's keyboard/tap activation, focus trap, Escape and focus return. It remains viewport-bounded on phones.
3. Tooltips contain short supplemental control names, not documentation or critical information. Use the narrow Radix Tooltip primitive for focus/hover, Escape and collision behavior. Icon controls keep explicit names independent of tips, and show names for coarse-pointer users.
4. Use the established Lucide vocabulary for common actions. `IconAction` is limited to conventional low-risk actions. Consequential actions retain explicit text, objects and review. PageAction/PageActionLink remain page commands; existing Dropdown Menu can group rare secondary actions. Shorten repeated nouns only when context is unambiguous.
5. Reserve Notice for actual warning/error/blocked/consequential states. Ordinary empty states use PanelMessage. PageHeader descriptions normally have zero or one short sentence; PanelHeader describes only its immediate task.
6. Product copy uses the user's mental model: what happened, what is visible, the next safe action and the consequence. Translate backend terminology through presentation helpers. Privacy-safe errors never reveal hidden existence, ownership, access rules or account state. Uncertain outcomes retain anti-duplication guidance.
7. Consent/privacy/security/governance decisions keep their required meaning visible before action. Active media, consent requests, denial/withdrawal and failures stay visible. Preserve institutional form questions, required guidance, response scales and user-authored content. Technical operators retain meaningful diagnostics and governance terminology; their general diagnostic limitations can be disclosed in Help.
8. Choose an editing surface by complexity: focused contextual Dialog for short entry/review, full pages for long forms. Preserve input, pending/error behavior, consequential review and focus return. Do not shrink typography to obtain density.

## Consequences

Help and named compact actions can be reused in future work, with a small Tooltip dependency rather than a new component system. Explicit page-level Help requires semantic review; mechanical rewrites and Help beside every field are not permitted. Accessibility and workflow tests cover the interaction contract rather than every editorial sentence.

The current E-Counseling change preserves Daily Prebuilt (`Daily.createFrame`), join/room security, media backend lifecycle, consent rules and reconciliation. A separate future PR will move to a Daily call object and COMPASS-owned call UI, reusing these primitives without preemptively duplicating call controls.

Implementation guidance: [frontend UI guideline](../../../fe/docs/ui-guidelines.md). Evidence and page matrix: [density audit](../../../fe/docs/ui-density-audit.md).

## Live session refinement (ADR-093)

[ADR-093](ADR-093-native-ecounseling-call-and-compact-session-workspace.md) is that future PR: the
E-Counseling session now uses a Daily Call Object with COMPASS-owned call controls (`CallControl`),
shared `Disclosure`/`DisclosureSection` progressive disclosure and named layout presets. `IconAction`
keeps its low-risk scope; recording and consent stay explicitly labelled and reviewed.
