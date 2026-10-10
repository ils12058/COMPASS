# UI information hierarchy and product voice

See [ADR-091](../../be/docs/decisions/ADR-091-ui-information-hierarchy-progressive-disclosure-product-voice.md) and the [page audit](ui-density-audit.md).

Show identity, current state, record content and the next useful action first. Keep warnings and required next steps visible. Classify explanation as state, next action, warning/blocker, consequence, conceptual explanation or input constraint before changing it.

Use zero or one short sentence under a page title. Panel descriptions explain the immediate task. Put longer conceptual explanations into grouped `ContextHelp` from the page header; use section Help only for a genuinely complex subsection. Never add a Help icon to every field. Field helpers stay short and input-specific.

Use `Tooltip` to name conventional compact controls outside normal page-header action slots. Every icon action has an accessible name independent of the tooltip. Use `IconAction` only for low-risk back/download/edit/more/refresh/search/settings; coarse-pointer users see the name too. Use the established Lucide vocabulary. Keep publication, issuance, finalization, deletion, recording, consent and account/security changes explicitly labeled.

Keep the primary next action visible. Existing Dropdown Menu may hold rare secondary actions. Use a focused Dialog for short contextual edits, a full page for large forms. Preserve unsaved input, pending dismissal rules, current/new review and deliberate focus return. Use `ConsequentialActionDialog` for significant consequences.

Reserve Notice for actual warnings, errors, blocked workflows and consequential outcomes. Ordinary empty states use PanelMessage. Keep persistent failures and uncertain results where the user can act; anti-duplication guidance must survive copy cleanup.

Describe what happened, what is visible, what the person can do and what happens next. Prefer familiar verbs, sentence case, concise sentences and natural professional contractions. Shorten repeated nouns when context supplies the object; preserve explicit accessible names. Translate implementation concepts through existing presentation helpers. Keep unknown backend messages out of product errors and preserve privacy-safe ambiguity.

Never disclose consent, privacy, security, retention/disposition, data release, irreversible publication or destructive consequences only through Help or hover. Consequences belong at the decision. Keep active recording/transcription, requested/declined/withdrawn permission, failures and important record facts visible. Preserve controlled/user-authored form questions, Privacy Notices, maintenance messages and record content. Density comes from hierarchy, not smaller text or indiscriminate hiding.

Verify keyboard and tap operation, Escape, focus return, named icon controls, tooltip focus/hover, persistent warnings, mobile wrapping and workflow consequences. Preserve existing authorization, wire contracts and ADR-090 sorting.

## Live sessions

See [ADR-093](../../be/docs/decisions/ADR-093-native-ecounseling-call-and-compact-session-workspace.md). Live-session workspaces prioritize the participant, connection state and immediate controls. Settled metadata and longer explanations use progressive disclosure (`Disclosure` for inline detail, `DisclosureSection` for a collapsible section whose one-line status stays visible). Consequential media actions remain visibly labeled and reviewed at the decision.

Layout density may change through named presets, but critical call/media state is never hidden: active recording/transcription, camera/microphone state, connection problems, pending decisions, denial/withdrawal, Leave and confirmation-time consequences stay visible in every preset and on phones.

Call controls use the feature `CallControl` tile (icon above a short visible label, at least 44px, label inside the accessible name), not `IconAction`. Local call controls act through the call client; recording, transcription, consent, downloads and retention act only through the COMPASS backend, and provider events only trigger a refresh of COMPASS state.

A joined E-Counseling call belongs to the authenticated portal session, not to one page ([ADR-094](../../be/docs/decisions/ADR-094-persistent-ecounseling-runtime-and-global-call-continuity.md)). Internal portal navigation preserves the call through a compact call dock; full call controls return when the person opens the active E-Counseling session. Never warn that portal navigation ends a call, and keep unsaved-change guards separate from call continuity. The dock shows who, connection, capture and immediate call controls only.

Cross-route call continuity does not make governed recording/transcription browser-local actions; COMPASS backend authority remains unchanged. Starting capture stays on the expanded session with its confirmation; the dock may offer the Counselor's protective stop and points the Student to pending decisions without deciding them.


## Structural and interaction conventions

`PageHeader` owns the page H1 and the gap before its working region. Use `back` for a text link
(`pageBackLinkClass`, “Back to …”), `description`/`context` for context, `meta` or children for facts,
`help` for grouped ContextHelp, and `actions` only for genuine page commands. Help shares the
navigation row when Back is present; it remains a separate slot and control. Feature headings
forward these roles; status and submission dates never occupy action slots. Back destinations and
unsaved-change guards remain feature-owned; the arrow is decoration, never part of the text label.

Every standard header command uses `PageAction`/`PageActionLink`, optionally `PageActionGroup`.
Labels stay visible below the icon on desktop, mobile, keyboard and touch. Links navigate, buttons
act/open a dialog; keep refs, complete accessible names, focus, pending and disabled states. Use
secondary for supporting commands. Consequential triggers keep explicit labels and their existing
review dialogs; danger uses the existing danger tokens. Forms, rows, contextual regions and dialog
confirmation controls use Button. E-Counseling's labeled layout preset controls are view preferences
that keeps its specialized behavior beside the commands; CallControl remains for live call controls.

A PanelHeader names a distinct region; a results panel immediately after an identically named page
uses “Results”, retaining its H2 and landmark ID. Use PanelSection for meaningful groups within one
sheet, PanelFooter for form submission, and avoid panel nesting. Collections use workspace width;
other pages use pageSheetWidth. Wrap text and actions and contain dense tables in local scrollers.

Portal collection search/filters use FloatingListTools; sorting and result context belong with
results. Public filters, report parameters, schedules, workflow selectors and conversations retain
their in-flow interfaces. Preserve defaults, submission timing, URLs, pagination and server queries.

LoadingRegion/RowsSkeleton describe initial loading. PanelMessage describes an empty/error state
inside a results panel; Notice describes a standalone contextual message; WorkspaceUnavailable
represents the whole inaccessible workspace. Preserve existing refresh/cache and access decisions.
Identical generic Active/Inactive indicators share ActiveStatusBadge; Legacy, Retired and workflow
statuses keep their domain presentation and text cues.

The AST header guard in tests/page-header-contract.test.mjs scans actual usage sites and forwarding
wrappers, following imported action components. It rejects raw/icon-only commands, metadata in
commands, unlabeled page actions, and misplaced back/help; representative negative fixtures prove
those rules. See [the Slice 1 audit](frontend-consistency-slice1.md) for evidence and exceptions.
