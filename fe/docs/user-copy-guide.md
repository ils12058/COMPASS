# COMPASS user copy

Write calm, concise, professional English for the person and their task. Explain what happened, its practical effect, and the next safe step when needed. Use natural contractions ("Couldn't load the referral. Try again."). Avoid playful errors, generic success claims, implementation narration, and unnecessary apologies.

## Names, grammar, and audience

Use sentence case for commands, ordinary nouns in prose, loading, errors, and empty states. Keep established workspace names in navigation and titles: Assessment Records, Routine Interviews, Individual Inventory, Guidance Operations, Graduate Tracer, Good Moral, Call Slips, E-Counseling. Keep institutional instrument names and section labels faithful to their source. Use Counselor and Guidance Services Staff for designated role labels; use student, counselor, college, and academic year as ordinary nouns in sentences. Head Guidance Counselor is a designation, not a separate account role. Guidance Office is the short task label; Guidance and Counseling Office is the formal office name. Preserve formal names and abbreviations such as CSM, MFA, PDF, and CSV.

Student copy explains their next step. Counselor/GSS copy uses needed record and workflow terminology without claiming duties beyond existing access. Administrative copy may retain capability overrides, retention, disposition, infrastructure, and configuration when these describe the administrator's actual work. Do not add role checks to vary style.

## Commands and accessible names

Use verb + object when context needs the object. Save preserves changes/drafts; Submit completes a submission step; Record documents an event/result; Finalize makes a record final; Issue formally issues a document; Publish makes approved content visible; Archive, Void, Withdraw, Cancel, Complete, and Reopen retain their distinct workflow meanings. Never substitute a generic Confirm for a consequential action.

Slice 1's PageAction/PageActionLink labels stay visible. labelDetail is a **suffix**, not a word inserted before the object: "Record" + "assessment result" reads "Record assessment result". "Record result" + "assessment" is awkward. Use the complete phrase visibly when a suffix cannot form a natural name. Pending labels name only the action actually underway. Back stays a link; no new icons, tooltips, layout patterns, or live regions are needed for editorial changes.

Use Search, Filters, Apply filters, Clear filters, Results, and Retry consistently. Preserve explicit Search/Enter in Accounts and existing instant search elsewhere. Previous/Next are acceptable beside Page N; accessible names must remain clear in context.

## Errors and recovery

Translate authoritative backend codes and HTTP statuses into frontend-owned copy. Never infer a backend condition from an unfamiliar English message. Unknown conditions use the caller's safe fallback. Don't render diagnostics from error.message or readApiErrorMessage by default. Preserve useful structured field locations through an allowlist of visible field labels; never echo unknown internal paths or field names.

Examples from COMPASS:

| Before | Preferred | Condition |
| --- | --- | --- |
| The Call Slip request contains a value that was not accepted. | Some call slip details need attention. Review them and try again. | Known validation rejection |
| The configured Routine Interview form revision is not supported for new records. | The current Routine Interview form can't be used to start a new interview. Contact the Guidance Office administrator. | Unsupported instrument; no invented workaround |
| Current operational workload and schedule within your authorized scope. | View the work you can act on and the current schedule. | Guidance Operations purpose |
| Your account can no longer open My actions. | You don't have access to My actions. | Confirmed access denial; don't guess the account's role |

A workspace access denial may say "You don't have access to referrals." A concealed record stays "This referral is unavailable." Never disclose existence, capability codes, confidential relationships, tenant boundaries, or sensitive internal reasons. Keep forbidden/not-found handling and cached-data concealment unchanged.

A conflict doesn't necessarily mean that a record changed. When one code covers changed state, eligibility, linked records, and invalid current choices, ask the user to review the relevant details without inventing a cause. Say the latest details are shown only where the workflow actually reloads them; keep refresh-failure warnings.

## Uncertain results and consequences

A failed connection doesn't prove a failed mutation. Retain "could not be confirmed" for uncertain booking, sending, recording, submission, issuance, and cancellation. Never say "not submitted" or invite a new request when the recovery retains the original identity. Preserve same-details/same-response Retry and deliberate editing as a new intent. Preserve in-progress, rejected, already processed, stale, and unavailable distinctions. Success follows backend confirmation; do not promise completed email, notification, release, or background work unless confirmed.

Keep all material consequences at the decision: reversibility, linked records, historical availability, access changes, notifications, and privacy/security effects. Help must never be the only place they appear.

## Everyday messages

Loading: "Loading referrals…", "Loading appointments…", "Checking available times…". Formal instrument names may remain capitalized. One busy region and one polite announcement; don't add duplicate announcements.

Empty: distinguish no existing records, no filtered matches, no records available to this reader, no remaining work, an empty later page, and a load failure. "No services have been added yet" is appropriate only for a successful unfiltered catalog including inactive services. "No active services are currently available" has a different meaning. Preserve "You're all caught up." for My actions.

Success: "Changes saved.", "Draft saved.", "Referral recorded.", "Call slip issued." Only add next-step/consequence details when needed.

## Controlled wording and intentional exceptions

Do not edit official Inventory/Exit/Routine/Tracer/Feedback questions, instrument sections, certificates, approved notices, consent/privacy/legal disclosures, historical snapshots, user-authored content, imported records, or external documents. Application loading, navigation, instructions, and errors are separate from these sources.

Existing Announcement/Resource/Privacy exact-message allowlists remain bounded compatibility translations inside stable-code branches: unknown messages use safe fallbacks. More precise stable subcodes require backend work. Password-policy structured messages are intentionally display-safe backend-authored validation (verified in authentication/password_access.py); don't change the policy. Good Moral's future-date message names the affected certificate date and is controlled staff guidance (verified in good_moral/services.py); keep this useful specificity. Administrative retention and infrastructure terminology is legitimate where necessary, not banned vocabulary.

Before handoff, exercise real message producers and rendered accessible names, preserve Slice 1 guards, and validate keyboard/dialog behavior and narrow-screen wrapping with synthetic data. Never claim live-backend or legal approval from a fixture test.
