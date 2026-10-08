# UI information hierarchy and product voice

See [ADR-091](../../be/docs/decisions/ADR-091-ui-information-hierarchy-progressive-disclosure-product-voice.md) and the [page audit](ui-density-audit.md).

Show identity, current state, record content and the next useful action first. Keep warnings and required next steps visible. Classify explanation as state, next action, warning/blocker, consequence, conceptual explanation or input constraint before changing it.

Use zero or one short sentence under a page title. Panel descriptions explain the immediate task. Put longer conceptual explanations into grouped `ContextHelp` from the page header; use section Help only for a genuinely complex subsection. Never add a Help icon to every field. Field helpers stay short and input-specific.

Use `Tooltip` to name conventional compact controls. Every icon action has an accessible name independent of the tooltip. Use `IconAction` only for low-risk back/download/edit/more/refresh/search/settings; coarse-pointer users see the name too. Use the established Lucide vocabulary. Keep publication, issuance, finalization, deletion, recording, consent and account/security changes explicitly labeled.

Keep the primary next action visible. Existing Dropdown Menu may hold rare secondary actions. Use a focused Dialog for short contextual edits, a full page for large forms. Preserve unsaved input, pending dismissal rules, current/new review and deliberate focus return. Use `ConsequentialActionDialog` for significant consequences.

Reserve Notice for actual warnings, errors, blocked workflows and consequential outcomes. Ordinary empty states use PanelMessage. Keep persistent failures and uncertain results where the user can act; anti-duplication guidance must survive copy cleanup.

Describe what happened, what is visible, what the person can do and what happens next. Prefer familiar verbs, sentence case, concise sentences and natural professional contractions. Shorten repeated nouns when context supplies the object; preserve explicit accessible names. Translate implementation concepts through existing presentation helpers. Keep unknown backend messages out of product errors and preserve privacy-safe ambiguity.

Never disclose consent, privacy, security, retention/disposition, data release, irreversible publication or destructive consequences only through Help or hover. Consequences belong at the decision. Keep active recording/transcription, requested/declined/withdrawn permission, failures and important record facts visible. Preserve controlled/user-authored form questions, Privacy Notices, maintenance messages and record content. Density comes from hierarchy, not smaller text or indiscriminate hiding.

Verify keyboard and tap operation, Escape, focus return, named icon controls, tooltip focus/hover, persistent warnings, mobile wrapping and workflow consequences. Preserve existing authorization, wire contracts and ADR-090 sorting.

## Live sessions

See [ADR-093](../../be/docs/decisions/ADR-093-native-ecounseling-call-and-compact-session-workspace.md). Live-session workspaces prioritize the participant, connection state and immediate controls. Settled metadata and longer explanations use progressive disclosure (`Disclosure` for inline detail, `DisclosureSection` for a collapsible section whose one-line status stays visible). Consequential media actions remain visibly labeled and reviewed at the decision.

Layout density may change through named presets, but critical call/media state is never hidden: active recording/transcription, camera/microphone state, connection problems, pending decisions, denial/withdrawal, Leave and confirmation-time consequences stay visible in every preset and on phones.

Call controls use the feature `CallControl` tile (icon above a short visible label, at least 44px, label inside the accessible name), not `IconAction`. Local call controls act through the call client; recording, transcription, consent, downloads and retention act only through the COMPASS backend, and provider events only trigger a refresh of COMPASS state.
