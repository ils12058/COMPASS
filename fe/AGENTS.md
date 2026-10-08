# COMPASS Frontend Rules

These rules apply to all work under `fe/`.

They are permanent frontend architecture, interaction, visual, content, and integration rules.

A feature prompt may make a requirement more specific, but must not silently weaken these rules.

---

## 1. Authority and precedence

When sources disagree, use this order:

1. The current explicit user-approved feature specification.
2. The canonical backend OpenAPI contract at `../contracts/openapi.json`.
3. This `AGENTS.md`.
4. Current approved frontend architecture.
5. Archived or legacy frontend implementations only where explicitly permitted as visual reference.

Do not infer product requirements from old frontend code.

Do not infer backend behavior from desired UI wording.

If a requested frontend behavior has no canonical backend contract, report the gap rather than inventing an API or fake workflow.

---

# 2. Archived frontend code

Archived frontend directories are reference-only.

Do not:

* import archived code;
* modify archived code;
* copy old architecture;
* revive old DTOs;
* revive old API wrappers;
* revive old state providers;
* revive old navigation registries;
* revive old giant stylesheets;
* revive old workflow assumptions;
* reuse old copy merely because it exists.

The only automatically preserved visual identity from the prior frontend is the approved palette, typography, and visual assets documented below.

Everything else must earn its place in the new implementation.

## Approved visual asset exception

The following user-approved COMPASS assets may be reused from the archived frontend in the fresh implementation:

Brand assets:

```text
public/brand/campus-bg.jpg
public/brand/compass-mark.svg
public/brand/compass-open-graph.jpg
public/brand/ucn-logo.png
```

Illustrations:

```text
public/illustrations/gco-character-point-right.png
public/illustrations/gco-character-point-up.png
public/illustrations/gco-character-wave.png
public/illustrations/gco-characters.png
```

These files are explicit exceptions to the archived-frontend restriction. Their approval does not authorize copying old layouts or other visual architecture.

Use approved assets purposefully.

Do not:

* place character illustrations on every page;
* use them as decorative filler;
* repeat the same character in multiple nearby sections;
* turn administrative screens into mascot-heavy interfaces;
* distort, recolor, destructively crop, or apply gradients or glows over approved brand marks;
* use the campus image as an unreadable full-page background.

Preserve the aspect ratio and visual integrity of brand assets.

`public/brand/compass-mark.svg` was redrawn as a compass dial (user-approved, October 2026): a
brand maroon tile, a cream face with four cardinal ticks, and a needle centered on the face with a
maroon north half, a brand gold south half, and a pivot. Keep the needle centered and the colors
from the palette below. The app icons `public/brand/compass-192.png` and `compass-512.png` are
rendered from it as full-bleed squares, so regenerate them whenever the mark changes. The app's
`themeColor` and manifest colors use brand maroon and the Body color.

User-approved exception: on the maroon public footer, `public/brand/ucn-logo.png` may be
rendered in solid white with a CSS filter (`brightness-0 invert`), because the maroon mark is not
visible on that background. This does not permit recoloring brand marks anywhere else.

Character illustrations are appropriate primarily for public-facing, onboarding, empty-state, or friendly informational contexts where they genuinely support the message. They should normally not appear inside dense administrative workspaces.

Current placements: the group image in the public landing hero;
the pointing-up character in the public Announcements title band; and
the pointing-right character in the public Resources title band (`PublicPageHeader`
`illustration`). A character repeats only on pages that never appear together. Do not add one to
detail pages, the landing's lower regions, or portal screens.

---

# 3. Technology baseline

COMPASS uses:

* Next.js App Router;
* React;
* strict TypeScript;
* Tailwind CSS;
* pnpm;
* Orval;
* TanStack Query;
* Fetch;
* Lucide icons;
* small source-owned UI primitives.

Do not introduce another framework, router, server-state system, global store, CSS framework, or component system without explicit approval.

Do not opportunistically upgrade major dependencies during unrelated feature work.

---

# 4. OpenAPI is the wire-contract authority

The backend-owned contract is:

```text
../contracts/openapi.json
```

Generate API request functions, schemas, enums, query keys, and React Query integrations from the contract with Orval.

Generated code belongs under:

```text
src/lib/api/generated/
```

Generated code must not be manually edited.

Generated code is not committed unless repository policy is explicitly changed.

Never manually duplicate backend:

* request types;
* response types;
* enums;
* pagination schemas;
* operation IDs;
* route paths;
* error envelopes.

A handwritten UI type is justified only when it represents genuine presentation state rather than a renamed copy of an API schema.

---

# 5. Never invent backend behavior

Do not:

* fabricate endpoints;
* fabricate filters;
* fabricate query parameters;
* fabricate mutation routes;
* fabricate response fields;
* fabricate dashboard metrics;
* fabricate historical data;
* fabricate permissions;
* fabricate workflow transitions.

Frontend terminology may differ from backend terminology.

That does not imply a new backend route is needed.

Example:

```text
Frontend label:
Email Delivery

Canonical backend:
platformOperationsListEmailDeliveries
```

Search the generated OpenAPI operations by capability and semantics, not only by guessed route names.

If functionality genuinely does not exist, stop that part of the implementation and state the missing contract.

---

# 6. Authentication

COMPASS authentication uses:

```text
HttpOnly opaque session cookie
+
Django CSRF
```

Never implement:

* JWT auth;
* bearer auth;
* localStorage auth;
* sessionStorage auth;
* frontend-managed access tokens.

Do not attempt to read authentication credentials from JavaScript.

Browser requests use:

```text
credentials: "include"
```

Frontend route visibility and capability checks improve UX only.

They are not security enforcement.

The backend remains authoritative.

## Step-up (recent MFA)

The backend decides which actions need a recent authenticator verification and reports the
account's real state: `recent_mfa_required` when an authenticator is set up but was not verified
recently, and `mfa_setup_required` when the account has no authenticator. Read it with
`stepUpRequirement` (`src/features/account/security/step-up.ts`) and pass the result to
`StepUpDialog` as `requirement`: "verify" asks for a current code, "setup" never asks for a code and
links to authenticator setup. After either, the person submits again; nothing is replayed.

Handle step-up only where the backend keeps it: account security and access, organization scope,
academic years, the service catalog, maintenance, and Privacy Notice publication and retirement.
Operational retention rule activation/retirement and disposition approval/retry also require
backend step-up. Draft rules and holds do not require step-up (ADR-072).
Routine work (Appointments, Availability, Good Moral issuance, email retry, name and ID corrections,
Privacy Notice drafts) and Referrals and Call Slips have no step-up, so do not add authenticator
prompts or MFA pre-checks to them.

---

# 7. CSRF

Unsafe browser requests use the canonical backend CSRF bootstrap flow.

CSRF behavior must be centralized in the API transport.

Do not:

* hardcode Django's CSRF cookie name;
* make each feature fetch its own CSRF token;
* store CSRF values persistently;
* automatically replay arbitrary failed unsafe requests.

An in-memory CSRF cache is acceptable.

On a canonical `csrf_failed` response, the cached token may be cleared.

Do not automatically repeat the mutation.

---

# 8. Same-origin API boundary

Browser code calls:

```text
/api/v1/...
```

The frontend may proxy/rewrite that same-origin path to a local backend using the server-owned:

```text
COMPASS_API_BASE_URL
```

Do not scatter absolute backend URLs through feature code.

Do not create feature-specific HTTP clients.

---

# 9. API transport

One shared transport owns:

* request URL normalization;
* cookies;
* CSRF;
* response parsing;
* binary response handling;
* structured API errors.

It must fail closed when generated code tries to request a URL outside the expected COMPASS API boundary.

Do not silently coerce malformed responses into successful-looking UI state.

---

# 10. Server state

Use TanStack Query for remote state.

Use React state for local UI state.

Do not rebuild server-state infrastructure with:

* `useEffect` request loops;
* homemade caches;
* custom request registries;
* page-wide loading booleans;
* custom focus listeners;
* arbitrary polling loops.

Use generated query keys where available.

Invalidate or refresh only affected data after successful mutations.

Do not invalidate the entire application cache after every write.

## Freshness by domain

The portal's defaults (30-second `staleTime`, no refetch on focus) suit most pages. Data that other
people change within seconds sets its own policy on its own queries instead of changing the
defaults. Appointment slot pickers use `appointmentSlotFreshness`
(`src/features/appointments/appointment-slot-freshness.ts`): a recheck every 15 seconds while the
page is visible, on window focus, and when the connection returns. A chosen time that a recheck no
longer offers is dropped, booking and rescheduling recheck the time before submitting, and a time
taken in between ("That time was just taken. Choose another available time.") reloads the times.
The server still decides every booking.

## Stale state

When an action finds the record changed, recover by what is on screen:

* selectable options (slots): reload them and drop a choice they no longer offer;
* read-only details and available actions: reload them and say briefly what changed ("This
  appointment was updated before your action completed. The latest details are now shown.");
* an open confirmation: close it and reload, so the person reviews the current actions again;
* a form with unsaved input: keep the input, load the saved version separately, say what changed,
  and allow saving again only after a deliberate review (the Privacy Notice draft editor);
* a reload that fails: keep the last confirmed data marked as not confirmed (`RefreshFailureNotice`),
  keep actions that depend on it unavailable, and offer Retry.

Never resubmit a consequential action automatically after a reload. Do not ask the person to
refresh what COMPASS has already reloaded; keep Retry or Refresh only when the reload failed or
COMPASS did not reload. Do not key an editor on a server timestamp: a background reload would
replace what the person typed.

---

# 11. Global state

Do not add Redux, Zustand, MobX, or another global store simply for convenience.

Add a global client-state solution only if a demonstrated cross-application state problem cannot be handled cleanly through:

* server state;
* route/search parameters;
* React composition;
* small local context.

---

# 12. Server and Client Components

Default to Server Components when browser interaction is not required.

Use Client Components for:

* interactive controls;
* dialogs;
* forms;
* TanStack Query hooks;
* browser-only APIs.

Do not put `"use client"` on a large route tree merely to make development easier.

Keep client boundaries small.

Avoid giant client components containing an entire application module.

---

# 13. Feature organization

Organize substantial frontend work by product feature/domain.

Prefer:

```text
src/features/accounts/
src/features/platform/
src/features/organization/
```

with components, presentation helpers, forms, and feature-specific logic colocated where appropriate.

Do not create giant global dumping grounds such as:

```text
src/components/everything
src/hooks/everything
src/services/everything
src/utils/everything
```

Shared primitives belong in bounded shared locations only when genuinely reusable.

---

# 14. Components

Split code by responsibility.

A page should compose features.

It should not contain an entire operational module in one file.

Separate meaningful responsibilities such as:

* page composition;
* list/filter controls;
* table/list presentation;
* record detail;
* forms;
* mutation controls;
* contextual panels.

Do not abstract prematurely.

Two vaguely similar elements are not automatically a shared component.

---

# 15. Approved typography

Primary UI/body font:

```text
Plus Jakarta Sans
400
500
600
700
```

Heading font:

```text
Outfit
500
600
700
800
```

Use `next/font/google`.

Canonical variables:

```text
--font-plus-jakarta
--font-outfit
```

Public-site script accent (user-approved):

```text
Caveat (variable)
--font-caveat
```

Caveat is loaded only by the public route layout and used only for the public landing hero quote
(Tailwind `font-script`). Do not use it in authenticated screens or for body copy.

Do not add additional display fonts merely to make a screen look distinctive.

---

# 16. Approved palette

These values are canonical COMPASS visual identity tokens.

```text
Ink                   #222a2d
Muted text            #59636a
On brand              #ffffff

Brand maroon          #6b1f2a
Brand maroon strong   #4d1520
Brand maroon soft     #8a3340
Brand gold            #936515

Support               #587466
Support strong        #36584b
Support soft          #dfe9df

Success               #356b49
Info                  #326676
Warning               #805700
Danger                #a52c35

Body                  #f7f3ea
Surface               #fffdf8
Raised surface        #ffffff
Muted surface         #edf1e8
Subtle surface        #f4efe4

Border                #d8d7cb
Strong border         #aeb3aa
```

Define and consume these through semantic tokens.

Two structural tokens are derived from Brand maroon with `color-mix` rather than added as new hues
(§68):

```text
brand-line   maroon-tinted line that frames working surfaces
brand-wash   pale maroon tint for table heads and action bands
```

Neither carries text contrast on its own.

Do not scatter raw hex literals through components.

Do not invent additional brand colors casually.

New functional colors require a concrete semantic need.

---

# 17. Light-first interface

COMPASS currently uses an intentional light interface.

Do not implement dark mode automatically.

Do not infer that every modern application requires theme switching.

A future explicit specification may introduce it.

---

# 18. Anti-AI-slop rule

The interface must not resemble generic AI-generated SaaS UI.

Do not default to:

* unrelated, gratuitous, or decorative gradients outside the approved branded treatment;
* gradient text;
* glassmorphism;
* frosted panes;
* blur blobs;
* neon glow;
* excessive shadows;
* oversized rounded rectangles;
* huge border radii;
* every section being a card;
* nested cards;
* gradient icon circles;
* fake analytics;
* fake trend indicators;
* fabricated KPIs;
* decorative percentage scores;
* meaningless charts;
* dashboard filler;
* generic hero sections inside the authenticated application;
* excessive hover elevation;
* springy/bouncy animation;
* motion added only to look premium.

Prefer useful institutional software over visual spectacle.

Restraint alone is not the goal either. A cream canvas, large whitespace, thin gray rules, minimal
surface boundaries, and muted copy, repeated on every page, is its own generic AI/SaaS look. §68
defines the institutional grammar COMPASS uses instead.

## Branded gradients

Gradients are not a general COMPASS interface pattern.

A restrained branded gradient using only the approved maroon and support or sage families may be used on:

* the public landing hero;
* authentication entry surfaces;
* closely related public or onboarding surfaces where the same visual identity is appropriate.

Preferred color families:

Maroon:

```text
#4d1520
#6b1f2a
```

Support or sage:

```text
#36584b
#587466
```

Do not introduce unrelated blue, purple, cyan, neon, rainbow, or multi-brand gradient combinations.

Do not use branded gradients as default backgrounds for:

* administrative workspaces;
* tables;
* cards;
* dialogs;
* forms;
* navigation;
* ordinary authenticated content sections.

Gradient use must preserve strong text contrast and remain subordinate to content.

Approved campus imagery may be softly blended into these branded background treatments where appropriate. Do not use this exception to obscure the image, reduce readability, or apply gradients over official COMPASS or UCN brand marks.

---

# 19. Cards must earn their existence

Use a card when the content is an independently meaningful grouped object or summary.

Do not use cards as the default wrapper for:

* every form section;
* every heading;
* every table;
* every number;
* every paragraph;
* every toolbar.

Use:

* hierarchy;
* a working surface (`Panel`, §68) around controls or records that belong together;
* sections inside one surface;
* tables;
* lists;
* borders and dividers that mark real divisions;
* tabs;
* whitespace

when they communicate structure better.

A `Panel` is not a card: it frames a functional region such as a filter's results, a record, or a
form. Do not answer missing structure by putting every section in its own card, and do not nest
panels.

---

# 20. Rounded shapes

Use restrained corner radii.

Do not make every:

* button;
* input;
* table;
* panel;
* badge;
* navigation link;
* filter;
* card

a pill.

Pills are appropriate for compact statuses, tags, or choices where the shape supports meaning.

---

# 21. Eyebrow text

Eyebrow text is exceptional.

Do not automatically put tiny uppercase text above every title.

Use an eyebrow only when it provides information not already carried by the heading, such as:

* parent context;
* category;
* record type;
* hierarchy;
* status.

Do not repeat the heading using alternate words.

Bad:

```text
PLATFORM OPERATIONS
Platform Health
```

if both merely identify the same page.

---

# 22. Page headings

A page title does not automatically require:

* eyebrow;
* subtitle;
* paragraph;
* icon;
* decorative card.

If the title communicates enough, stop there.

Supporting text is appropriate only when it clarifies real:

* scope;
* prerequisites;
* consequences;
* policy;
* non-obvious workflow.

Render page titles with `PageHeader` (`src/components/ui/page-header.tsx`); feature heading wrappers
delegate to it. Keep the header compact so the page's own work starts in the first screen, and do
not draw a rule under it: the working region that follows carries its own boundary.

The header owns the one gap between the title and the page's first region, so every page starts
its work at the same distance. Feature wrappers do not remove it (`mb-0`) and the next region does
not add its own. Page actions line up with the title, not the description. Facts that describe
the page's subject, such as a record code or status, go in the header (`meta`, `description`, or
children), not in a separate row after it.

---

# 23. Product copy

COMPASS is university operational software, not SaaS marketing copy.

Write for the actual user and task.

Avoid filler language such as:

```text
seamlessly
effortlessly
empower
unlock
streamline
stay on top of
take control
powerful solution
robust experience
everything you need
designed for efficiency
```

unless the wording carries an actual required meaning.

Prefer:

```text
Accounts
Manage COMPASS accounts and access.
```

over:

```text
Empower your institution with seamless user management.
```

Do not narrate obvious controls.

## Explain through structure

COMPASS interfaces explain themselves through structure, labels, current state, and action
hierarchy. Interface copy is not documentation: prefer information density over explanation
density. A screen may carry a lot of useful information — identity, status, dates, context — without
paragraphs about what the screen is for.

Do not add copy merely because a page, panel, field, status, or control can be described. Text that
stays on screen earns its place by helping the reader:

* understand a non-obvious current state;
* choose the correct next action;
* avoid a meaningful mistake;
* understand a real policy, privacy, security, or consent consequence.

Ask of each sentence: if it were removed, would the reader be less able to complete the task
correctly and safely? If not, remove or shorten it. If so, keep it next to the decision or state it
concerns: the consequence of starting a recording belongs in its confirmation, not above the
workspace.

* Progressive disclosure: keep identity, current state, the primary action, and any warning that
  applies now visible; show validation, unavailable-action reasons, and consequences when they
  apply; keep rare actions and extended detail out of the way. Never put needed information in
  hover-only UI.
* State each fact once per view. Do not repeat the same status in a summary, a section, and a
  banner.
* Make the primary action obvious; destructive actions come last and are never the most prominent.
  Hide an action the reader has no reason to expect; explain one they would expect but cannot use.
* Student-facing screens answer "What is this? What is my status? What can I do next?" in plain,
  task-focused words. Translate backend states and implementation terms (provider, projection,
  reconciliation) through presentation helpers; administrative screens may keep operationally
  meaningful technical detail.
* Never delete safety-critical copy just to reduce text: confidentiality, consent, recording and
  transcription, Privacy Notices, security, access changes, maintenance, publication, issuance,
  and destructive or hard-to-reverse actions keep their explanation at the point of decision.
* Do not rewrite controlled or user-provided content (Privacy Notices, maintenance messages,
  institutional form wording, recorded content) to make a screen shorter.

---

# 24. Button copy

Use direct action labels.

Good:

```text
Save changes
Create account
Disable account
Enable account
Assign counselor
Remove designation
Schedule maintenance
Retry email
Cancel appointment
```

Avoid:

```text
Proceed
Take action
Continue journey
Get started
Let's go
Manage now
```

A destructive action must be labeled with the destructive action.

Do not hide it behind `Confirm`.

---

# 25. Empty-state copy

State the actual condition.

Prefer:

```text
No failed email deliveries.
```

over:

```text
You're all caught up! 🎉
```

Do not use fake cheerfulness in administrative or sensitive workflows.

An empty state belongs to the region it describes: inside the results or section panel
(`PanelMessage`), not as lonely text between two rules. Do not add illustrations, giant icons, or
celebratory copy.

---

# 26. Error copy

Use safe backend-provided information when available.

Explain:

* what could not be completed;
* why, when safe and known;
* what the user can do next.

Do not show:

```text
Oops!
Something went wrong!
```

as the universal error strategy.

Do not expose technical stack traces or secrets.

---

# 27. Dialog vs page

A dialog is appropriate for a short, focused, contextual interaction.

Examples may include:

* assigning a counselor;
* changing a role;
* adding a short exception;
* scheduling a simple maintenance window;
* setting a small capability override.

Use a dedicated page or large page section for:

* multi-section forms;
* many fields;
* imports/uploads;
* complex validation;
* long workflows;
* record editing that requires substantial context;
* tasks where the user will spend significant time.

Do not put giant workflows in small scrolling dialogs.

---

# 28. Confirmation dialogs

Do not make every mutation require confirmation.

Confirmation fatigue reduces safety.

Require explicit confirmation for consequential actions, including:

* destructive changes;
* difficult-to-reverse changes;
* state transitions with significant consequences;
* changes to another user's access;
* security administration;
* high-trust operations.

Examples:

* disable account;
* change account role;
* assign/remove institutional designation;
* grant/deny/remove capability override;
* reset MFA;
* revoke sessions;
* revoke trusted browsers;
* enable/disable maintenance;
* schedule/cancel maintenance;
* void/cancel/finalize/publish/issue/reopen consequential records.

Ordinary `Save changes` does not need an additional confirmation by default.

Build confirmations with `ConsequentialActionDialog` (`src/components/ui/consequential-action-dialog.tsx`).
It owns the pending, dismissal, and inline-error behavior. The feature supplies the meaning: title,
consequence, action and pending labels, primary or danger variant, and error mapping. Do not
assemble a confirmation from `Dialog`, and keep data entry in a `Dialog` even when a review step
follows it.

When the outcome deserves acknowledgment where the reader acted, pass `completed` (a title, the
outcome, and optionally a Done label) once the backend confirms: the same dialog moves from
confirmation through pending and error to its outcome with a single Done, so the action cannot be
submitted twice and nothing reopens as a second dialog. Done takes focus and is described by the
outcome. When the opener no longer exists (the Remove button of a removed row), pass
`onCloseAutoFocus` and place focus deliberately (`focusHeading`, `src/lib/focus-heading.ts`).

---

# 29. Confirmation copy

Never rely on generic:

```text
Are you sure?
```

Identify the object, action, and meaningful consequence.

Good:

```text
Disable Reynan Tolentino's account?

They will no longer be able to sign in to COMPASS until the account is enabled again.

Cancel
Disable account
```

The user must know exactly what they are confirming.

---

# 30. Dialog accessibility

Use established accessible primitives.

Do not hand-roll:

* focus traps;
* keyboard dismissal;
* screen-reader dialog semantics.

Dialogs must:

* have an accessible title;
* have an accessible description when needed;
* trap focus correctly;
* return focus appropriately;
* support keyboard use.

Never nest modal dialogs.

`DialogContent` names its close button "Close dialog". Pass `closeLabel` when what the dialog holds
names it better, as the portal drawer does with "Close navigation". Confirmations have no corner
close button; they close through their labeled actions.

Focus returns to the control that opened a dialog, and after a two-step flow, such as a selection
followed by its review, to the control that started the flow. A dialog that places focus itself,
such as the Markdown link dialog, does so in `onCloseAutoFocus` by preventing the default.

---

# 31. In-flight dialogs

After a consequential mutation starts:

* prevent duplicate submission;
* show specific pending copy;
* keep the dialog stable;
* avoid ambiguous dismissal;
* do not close before success.

Success:

```text
mutation succeeds
→ close, or show the confirmed outcome in the same dialog (§28 `completed`)
→ invalidate/refresh affected data
→ provide appropriate feedback (§53)
```

Failure:

```text
mutation fails
→ stay open
→ preserve values
→ show error
→ allow retry
```

Do not optimistically announce a high-impact mutation as successful before the backend confirms it.

A `Dialog` that owns a request passes `dismissible={!pending}` to `DialogContent`. The close button
is removed, and Escape and outside clicks no longer close it, so do not intercept
`onEscapeKeyDown`, `onPointerDownOutside`, or `onOpenChange` for the same purpose. Disable the
dialog's own Cancel while pending.

---

# 32. Forms follow mutation contracts

Do not generate editable forms from GET/detail responses.

Use the corresponding mutation contract to determine what may be changed.

Read-only data stays read-only.

A field appearing in a response does not grant edit authority.

Do not merge distinct security workflows into ordinary profile-edit forms.

---

# 33. Form submission

While submitting:

* disable duplicate submit;
* show action-specific pending state;
* preserve layout;
* keep values;
* do not blank the form.

On backend validation error:

* preserve input;
* map safe field errors where possible;
* show a form-level error when appropriate;
* allow correction and retry.

Do not silently truncate user input merely to make it pass a request limit.

---

# 34. Unsaved changes

Untouched form:

```text
close normally
```

Dirty meaningful form:

```text
warn before destructive discard when appropriate
```

Do not warn when no changes exist.

Do not implement discard confirmations so aggressively that routine navigation becomes annoying.

---

# 35. Loading states

Do not treat loading as one giant global spinner.

Distinguish:

```text
initial loading
loaded
empty
error
background refresh
mutation pending
```

These states have different UI behavior.

---

# 36. Initial loading

For predictable structured pages, prefer layout-preserving skeletons.

Examples:

* table-row skeletons;
* detail-field skeletons;
* summary-block skeletons.

Do not use a huge centered spinner where the future layout is already known.

Avoid large layout shifts when content arrives.

Wrap an initial-loading region in `LoadingRegion` (`src/components/ui/loading-region.tsx`). It marks
the region busy and gives one polite status naming what is loading, and its Skeleton shapes stay
hidden from assistive technology. A route-level Suspense fallback reuses the feature's own loading
state rather than a generic block.

---

# 37. Background refresh

If valid data is already visible, do not destroy it merely because a refetch began.

Retain existing content when safe.

A subtle refresh indicator may be used when useful.

Do not re-skeletonize the whole screen during routine background refresh.

---

# 38. Mutation pending state

Scope pending state to the affected action.

Example:

```text
Disable account
```

becomes:

```text
Disabling…
```

Do not freeze unrelated page content unless correctness requires it.

Prevent double-submission.

---

# 39. Loading is not empty

Never render:

```text
No records found
```

while the initial request is unresolved.

Only show the empty state after a successful request confirms zero results.

---

# 40. Partial failures

A secondary panel failing should not automatically replace the whole page with an error screen.

Keep unaffected information usable where safe.

Present the failure at the smallest meaningful scope.

---

# 41. Optimistic UI

Do not use optimistic updates for:

* access changes;
* security operations;
* irreversible/destructive actions;
* significant lifecycle transitions;
* privacy-sensitive operations.

Wait for backend confirmation.

Optimistic updates for low-risk reversible interactions require deliberate product justification.

---

# 42. Accessibility

Accessibility is required, not optional cleanup.

Use:

* semantic HTML;
* real buttons;
* real links;
* labels tied to controls;
* keyboard-accessible interaction;
* visible focus;
* adequate contrast;
* semantic tables for tabular data;
* appropriate `aria-live`;
* appropriate `aria-busy`;
* reduced-motion handling.

Do not make clickable `<div>` elements imitate controls.

Do not hide focus indicators.

Readers can enlarge text, add spacing, underline links, and reduce motion from the Accessibility
control (`src/features/accessibility/`). Keep text and layout sizes in `rem` so the Text size
setting scales them.

The portal shell owns the one "Skip to main content" link and its `main#main-content` target. Do not
add per-page skip links or a second `<main>`.

Every dock destination keeps its label as its accessible name, even while the dock shows icons
only; the visible tip on hover and keyboard focus repeats that name and is hidden from assistive
technology. The control that expands and collapses the dock is an icon button at the start of the top
bar, outside the list of destinations, with an accessible name and `aria-expanded`.

Links between sections of one workspace sit in a `<nav>` named "<Workspace> navigation". Mark the
current page with `aria-current="page"`, and keep each navigation link at least `min-h-11` tall.

Announce each message once: do not put a `role="alert"` or `role="status"` element inside an
`aria-live` container.

Form controls use the shared `Input`, `Textarea`, and `Select` (`src/components/ui/`) instead of
hand-written class strings. Each shows `aria-invalid="true"` with a danger border, so a field the
form already knows is invalid looks invalid as well as being described by its error text.

A link that navigates but is presented as an action stays a link and takes the button styling:
`<Link className={buttonVariants({ variant: "secondary" })}>`. Actions that change data stay
`<Button>`. Ordinary text links keep text-link styling.

---

# 43. Responsive behavior

All user-facing screens must remain usable at narrow widths.

Do not design only for one desktop screenshot.

For dense administrative content:

* preserve readability;
* use deliberate horizontal table strategies;
* collapse secondary information intelligently;
* do not convert every table into unreadable card spam merely to claim mobile responsiveness.

Responsive design must preserve task clarity.

---

# 44. Motion

Motion must communicate:

* state change;
* continuity;
* focus;
* opening/closing relationships

rather than decoration.

Keep transitions restrained.

Respect:

```text
prefers-reduced-motion
```

JavaScript-driven motion must use `useReducedMotion()` from
`src/features/accessibility/use-accessibility-preferences.ts`, which combines the operating-system
setting with the reader's COMPASS "Reduce motion" setting. CSS transitions are covered globally.

Do not add bounce, spring, hover-lift, or continuous animation merely to make the interface feel modern.

The portal dock's expansion and the floating list tools that follow it use one short width or
position transition, which the reduced-motion settings shorten to an instant change.

---

# 45. Icons

Lucide icons are the default general-purpose icon set for COMPASS.

They may support both functional interface meaning and restrained decoration.

Functional uses include:

* search;
* filter;
* calendar;
* download;
* external links;
* notifications;
* account actions;
* navigation;
* status or action affordances.

Decorative use is allowed when it strengthens hierarchy or communicates the subject of a section, but it must remain secondary to the content.

Icons are not decoration quotas.

Do not:

* add an icon to every heading;
* create an icon circle for every section or card;
* use icons merely to fill empty space;
* use multiple decorative icons around one message;
* substitute Lucide icons for official COMPASS or UCN brand marks;
* make iconography the primary visual language of dense administrative pages.

Decorative icons should normally use restrained sizes and semantic token colors.

If an icon is purely decorative, hide it from assistive technology with `aria-hidden="true"`.

If an icon performs an action or conveys information not present in text, provide an accessible name or accompanying text.

Critical actions require text labels unless a universally understood icon has an accessible name and the context makes the action unambiguous.

---

# 46. Tables and operational lists

Use a table when users need to scan or compare the same fields across many records.

Typical table examples include:

* accounts;
* email deliveries;
* appointments;
* referrals;
* call slips;
* organizational assignments;
* service records.

Use a list when each record is primarily read as one compact narrative or status item rather than compared column by column.

Typical list examples include:

* notifications;
* activity history;
* audit or activity projections;
* workflow timelines;
* announcements.

Do not turn dense administrative data into a wall of oversized cards.

Do not use a card grid merely to avoid building a responsive table.

## Table structure

A table must have a clear primary column representing the record identity.

Keep columns limited to information useful for scanning and decision-making. Do not expose every response field as a table column.

Move secondary information to:

* record detail;
* expandable context;
* secondary text;
* a contextual action menu.

Avoid tables wider than necessary.

A results table sits flush inside a `Panel` whose `PanelHeader` names the results and gives their
context (`describeResultPage`). Style it with the shared `dataTable` classes
(`src/components/ui/data-table.ts`): the maroon-washed head is the table's emphasis, rows are
separated by ordinary lines, and a sticky identity column keeps the row background. Do not add
heavy full-color header chrome or zebra stripes.

## Row actions and selection

Use a dedicated actions column only when rows genuinely have multiple contextual actions.

Prefer:

* clicking the primary record link or title to open detail;
* one clearly visible primary row action when appropriate;
* an overflow menu for secondary actions.

Do not place five to eight full-size buttons in every row.

Consequential row actions still require the standard confirmation flow.

Do not add checkboxes or bulk-selection UI unless the product explicitly supports a real bulk operation.

Do not create disabled-looking bulk toolbars for future features.

## Responsive tables

Do not automatically convert every table into a card stack on mobile.

For dense administrative data, preserve comparison semantics.

Preferred strategies:

* allow deliberate horizontal scrolling;
* keep the primary identity column readable;
* hide or collapse truly secondary columns;
* move secondary details into the detail page.

Do not duplicate all columns into verbose mobile cards.

## Operational lists

Operational lists should have a consistent row anatomy where useful:

```text
primary identity
secondary context
status
relevant timestamp
contextual action
```

Do not decorate every list row with oversized icons, gradients, cards, or avatars unless those elements communicate actual information.

Lists must account for:

* loading;
* empty;
* error;
* filtering;
* pagination;
* row actions;
* keyboard/accessibility behavior.

## Pagination

Use the canonical backend pagination state:

```text
items
page
page_size
has_next
```

Do not invent page counts or total records.

When `has_next` is false, disable or omit Next appropriately.

Authenticated lists page with `CanonicalPagination`
(`src/features/portal/components/canonical-pagination.tsx`). It renders nothing for a single page
and stays on an empty later page so the reader can go back, so render it whenever the list has
loaded rather than only beside rows. The feature owns what `onPageChange` does, including which
search and filter parameters it keeps. Public pages keep `PublicPagination`, which uses real links.

## Empty results

Differentiate between:

* no records existing;
* no records matching the current filters or search.

For a filtered empty state, provide a clear way to clear or adjust filters.

Do not show a celebratory empty state for routine administrative data.

---

# 47. Search and filters

Use backend-supported parameters only.

Do not fabricate client-side global search over paginated server data and present it as complete.

Keep shareable/list-navigation state in URL search parameters when doing so materially improves navigation and return behavior.

Preserve search and filter state while moving between pages.

Reset to page 1 when a filter or search change invalidates the current page.

Do not add filters merely because a field exists in a response.

## Floating list tools (authenticated portal collections)

In the authenticated portal, the search and filters of a collection — a record list, directory,
administrative table, or work queue — are tools for that collection, not a region of the page. They
float near the bottom of the workspace in `FloatingListTools`
(`src/components/ui/floating-list-tools.tsx`), and the records start right after the page header.

* The collection's text search leads the bar (`ListSearchField`). A collection whose only filter is
  one short choice puts that choice in the bar instead (`ListToolField`, `compact`).
* Structured filters open from a `Filters` button that counts the ones in use (`filterCount`, from
  the applied results, counting a filter only when it differs from its default). They open above the
  bar on wider screens and as a bottom sheet on phones. The panel is a native modal `<dialog>` that
  stays inside the feature's form while closed, so filters keep applying while they are out of
  view.
* Messages about how filters were applied, such as a cleared Missing filter, stay on the page above
  the results. A filter value the feature refuses to apply, such as a From date after the To date,
  is shown in the panel; pass `invalid` so submitting opens the panel to show it.
* `Clear filters` sits in the panel (or in the bar when there is no panel) only while a filter is
  active.
* The tools center on the workspace, not the window: the shell publishes where the workspace begins
  (`--portal-content-inset`) and keeps the last records and pagination clear of the tools while they
  are on the page (`--list-tools-clearance`). Features do not add their own offsets or bottom space.
* Pagination stays with the results (`CanonicalPagination`). The floating tools find, filter, and
  refine; they do not page.

Use them only for a collection's own search and filters. Forms, report parameters, schedule
editors, configuration pages, record details, creation and editing screens, and workflow selectors
keep their controls in the page. A page that opens a form over its list, such as recording a
Counseling encounter, hides the tools while that form is open.

## Filter toolbar (public pages and in-flow filters)

The public Announcements and Resources pages, and parameter forms that are not collection tools
(such as a report's filters), keep their controls in the page in one `FilterToolbar`
(`src/components/ui/filter-toolbar.tsx`) between the page header and the results, so they read as
one tool rather than inputs placed on the page.

## Both

Label each control (`FilterField`, or the visually hidden label of `ListSearchField`). Do not add a
large "Filters" heading when the controls already say what they do.

Every control in one set of filters applies the same way:

* explicit: one form, one submit (`Apply filters`, or `Search` beside a search field in the bar),
  and Enter in the search field submits the same form. This is the default when a free-text search
  sits beside other filters.
* immediate: each change applies. Use it for a few selects or dates without free-text search, or
  for a lone debounced directory search.

Do not give the search field its own Search button while neighboring filters apply on change. Show
`Clear filters` only while a filter is active. Controls that hold a text search sit in a form with
`role="search"` and an accessible name.

A long in-flow toolbar folds its secondary filters away. When a text search sits beside more than
two other filters, pass the others as `advanced`: the search, a `Filters` button, and the actions
share one row, and the advanced filters open below it, starting open while any is in use. Folded
fields stay in the form. Messages about how filters were applied stay outside the folded section.

---

# 48. Authorization-aware UI

Frontend access checks exist to:

* avoid presenting impossible actions;
* improve navigation;
* explain availability.

They do not provide security.

Do not scatter code like:

```ts
if (role === "IT_ADMIN")
```

when the actual decision is capability-based.

Do not infer confidential record scope from role names.

Backend authorization remains final.

---

# 49. Role and designation semantics

Do not collapse roles and designations into one frontend concept.

Examples:

```text
IT_ADMIN
COUNSELOR
GUIDANCE_SERVICES_STAFF
STUDENT
INSTITUTIONAL_OFFICER
```

are roles.

Examples:

```text
HEAD_GUIDANCE_COUNSELOR
DPO
```

are institutional designations.

Render them according to their actual semantics.

Do not assume Head Guidance or DPO is a standalone role.

---

# 50. Activity and audit terminology

Do not call every history/activity surface `Audit Logs`.

Different concepts exist:

```text
self account activity
security activity
platform activity
privacy activity
domain record history
```

Use the product-appropriate term.

Do not expose raw `AuditEvent` records through invented frontend behavior.

---

# 51. Domain history

A record lifecycle/history page must use a real backend history contract.

Do not reconstruct authoritative history from:

* current status;
* client logs;
* notification records;
* guessed timestamps.

If no history endpoint exists, do not fake a timeline.

---

# 52. Notifications

Notification UI follows the canonical current Notification contract.

Do not invent:

* archive behavior;
* bulk actions;
* notification categories;
* configurable mandatory-email suppression;
* backend status filters

unless the contract provides them.

Optional email preference only controls optional informational email.

Mandatory security and operational delivery remain backend policy.

---

# 53. Action feedback

Each outcome is shown where the reader can use it:

```text
field or form validation                → inline, at the field or the day/row it concerns
query or page load failure              → Notice / PanelMessage
refresh failure with last-known data    → RefreshFailureNotice, persistent
an action inside a dialog fails         → the dialog stays open and shows the error
routine change succeeds                 → ActionStatus, non-blocking and transient
consequential change succeeds           → its confirmation dialog completes in place (§28)
important change fails                  → persistent contextual error, never a disappearing message
```

`ActionStatus` and `useActionStatus` (`src/components/ui/action-status.tsx`) confirm routine success
only after the backend confirms it ("Weekly schedule saved.", "Profile changes saved."). The page
owns one status; a newer message replaces it. It floats at the bottom right of the workspace, above a
collection's floating tools when they are on the page and below dialogs; it is announced politely,
never takes focus, can be dismissed, pauses while pointed at or focused, and leaves after about five
seconds. Clear it when a new attempt starts, so an old confirmation never sits beside a new failure.

Never make it the only place for a failure, an uncertain result, a stale-state conflict, a security
problem, or anything the reader must act on. Do not add a toast library, and do not announce every
trivial action because a status component exists. Dialogs are for decisions, focused short entry,
and outcomes that deserve acknowledgment (a completed booking), not for routine "Saved" messages.

---

# 54. Design tokens

Colors, typography, spacing, radii, focus style, and other system values belong in bounded design tokens.

Feature code should not accumulate arbitrary one-off values.

However, do not create hundreds of speculative tokens.

A token exists because it represents a repeated semantic design decision.

---

# 55. CSS

Prefer:

* semantic tokens;
* Tailwind utilities;
* small bounded component styles when necessary.

Do not create:

* giant global feature stylesheets;
* feature-specific global selectors;
* unbounded `!important`;
* arbitrary style duplication.

Do not import CSS from archived frontend implementations.

---

# 56. Component libraries

A component library is implementation infrastructure, not COMPASS visual identity.

Do not paste demo components/layouts wholesale.

If using Radix or another behavior primitive:

* retain accessible behavior;
* apply COMPASS-owned styling;
* keep the dependency narrow.

Do not initialize dozens of unused components.

---

# 57. Generated code

Never edit:

```text
src/lib/api/generated/**
```

by hand.

If generated output is wrong:

1. inspect `contracts/openapi.json`;
2. inspect `orval.config.ts`;
3. inspect the custom mutator;
4. fix the correct source.

Do not patch generated files.

---

# 58. Dependencies

Every new dependency needs a concrete current requirement.

Do not add a package merely because it may be useful later.

Avoid overlapping libraries solving the same problem.

Do not retain old dependencies from archived code unless the fresh frontend actually uses them.

---

# 59. Safety for backend-owned files

Frontend feature work must not modify:

```text
be/**
contracts/openapi.json
```

unless the task explicitly includes an approved backend contract change.

If frontend implementation exposes a backend gap, report it.

Do not quietly modify backend code from a frontend task.

---

# 60. Validation

Before completing meaningful frontend work, run:

```bash
pnpm api:generate
pnpm lint
pnpm typecheck
pnpm build
```

Use more focused checks where appropriate during development.

Do not weaken lint/type/build rules merely to pass CI.

Run:

```bash
git diff --check
git status --short
git diff --stat
```

before handoff.

---

# 61. Review generated API changes

When `contracts/openapi.json` changes in a future backend merge:

1. regenerate;
2. inspect relevant generated operation/type changes;
3. update frontend intentionally.

Do not blindly accept generated breakage with type casts or `any`.

---

# 62. TypeScript

Keep strict TypeScript.

Avoid:

```text
any
@ts-ignore
@ts-nocheck
```

unless a narrowly documented external-library defect leaves no safer alternative.

Do not silence contract problems with type assertions.

Prefer narrowing over casting.

---

# 63. No fake success

Never show a success state merely because the user clicked a button.

Success follows confirmed backend success.

This is especially important for:

* security;
* account access;
* document issuance;
* workflow transitions;
* email retries;
* maintenance controls;
* privacy-sensitive operations.

---

# 64. No speculative product design

Do not create additional:

* pages;
* navigation entries;
* dashboard cards;
* tabs;
* filters;
* metrics;
* settings;
* bulk actions;
* workflows

simply because they seem useful.

Implement the approved specification.

If a meaningful improvement becomes apparent, report it rather than silently expanding scope.

---

# 65. No one-page-per-endpoint architecture

OpenAPI operations are not navigation requirements.

A page may coordinate multiple operations.

Several operations may belong inside one record-detail workflow.

Do not create navigation destinations merely because separate API endpoints exist.

The portal dock and the public landing's quick access read one access list,
`portalWorkspaceGroups` (`src/features/portal/components/portal-workspaces.ts`). It orders the
dock by how often the work happens: scheduling, records, requests and surveys, content, and
reports first; institution setup, identity and access, privacy governance, and platform operations
last. Add a workspace there, in the group where its daily use belongs.

Information architecture is product design, not an automatic projection of the backend router.

## Portal feature navigation

The dock is the browsable primary workspace structure. The top-bar Go-to command palette
(`Cmd/Ctrl+K`) indexes stable portal features, not records. Root visibility reuses
`portalWorkspaceGroups`; deep destinations reuse current access helpers and workspace gates.
Exclude dynamic record routes and destinations requiring record context. Build only authorized
commands, never unauthorized names hidden with CSS. Navigation uses the unsaved-changes guard;
the palette cannot execute mutations directly. Do not add record search, query logging, or search
history to feature navigation.

---

# 66. Administrative detail pages

Actions related to one resource should generally remain with that resource unless there is a genuine cross-resource workflow.

Example:

Account Detail may contain:

* identity;
* role;
* lifecycle;
* designations;
* effective access;
* capability overrides;
* session administration;
* MFA administration.

Do not automatically turn each API action into a separate navigation destination.

---

# 67. Definition of done

A feature is not done merely because the happy path renders.

Completion includes the relevant:

* loading state;
* empty state;
* error state;
* permission state;
* pending mutation state;
* confirmation behavior;
* keyboard behavior;
* responsive behavior;
* contract correctness;
* invalidation/refetch behavior;
* copy quality.

Do not defer these as generic polish unless the feature specification explicitly stages them.

---

# 68. Institutional visual grammar

COMPASS should look like a modern university service and records system with clear institutional
structure. It should not look like generic AI/SaaS minimalism, a card-heavy dashboard, a decorative
marketing site, or a dated Bootstrap university portal.

The approved formula: V1's structural clarity and useful density, plus V2's restrained maroon
framing, plus the current frontend's accessibility, typography, responsiveness, and workflow
semantics.

## Canvas and working surfaces

The warm canvas (`bg-body`) stays. It becomes generic only when every region sits directly on it,
separated by whitespace and a thin gray rule.

Areas where people work sit on a working surface, a `Panel`: white, framed evenly on every side by
`border-brand-line`, `rounded-sm`, no shadow. Examples:

* filter results;
* record summaries and detail groups;
* forms and workflow controls;
* Overview regions;
* the public landing's editorial regions.

A page can still have flat regions: the page header, running text, and short notices stay on the
canvas. Do not nest panels.

## Whitespace and density

Whitespace supports hierarchy; it does not replace it. Controls and information that belong
together are visibly grouped.

Prefer moderate density, as suits institutional software:

* compact page introductions;
* short gaps between related regions;
* several related pieces of information visible at once;
* no blank intervals without an information purpose.

Density never shrinks accessibility. Keep content text at `text-sm` or larger, use `text-xs` only for
labels and metadata, keep control targets at `min-h-10`/`min-h-11`, and keep readable line heights.
Desktop may use two columns and multi-column facts; phones stack instead of shrinking.

## Variable density

Regions do not all deserve equal weight. A working surface grows with its content, not with the
space the layout offers. `PanelMessage` sizes itself by what it says: a short muted message with no
action ("No counseling encounters are assigned to you yet.") is compact, so a sparse collection stays
shallow; a failure or a message with a Retry or next step keeps room for it. Pass `density` only to
override that for a reason. Do not shrink `Panel` padding globally or add page-specific padding
overrides to make a page look denser.

Flatten surfaces that are not separate regions: a bordered box inside a panel (Programs inside a
College, exceptions inside Unavailability) becomes rows, indentation, or dividers. Keep a boundary
where it marks a real separate thing: a selectable group, a form's scope, a table, a dialog, an
independent workflow.

## Asymmetric modular composition

Unequal spans are allowed where workflow importance is unequal: a primary working region beside a
narrower secondary one, with supporting regions below. Examples: the weekly schedule beside its
Unavailability with the preview below; Profile's identity beside its editable details; Health's
checks beside the background-worker check; Overview's work beside At a glance. Launcher pages
(Reports, Privacy Governance) may set their destinations side by side as framed links with a
restrained Lucide icon (about 20px), a title, and one factual line.

The composition is structural, never decorative:

* switch columns on at the region's own width (a container query), so an expanded dock stacks
  them instead of squeezing the primary region; phones stack;
* collections (record lists, queues, directories, Activity) stay dense tables and lists;
* no metric tiles, icon-and-number cards, charts, counts, or scores, and no card mosaics;
* no generic `BentoCard` or second card system: a `Panel` is still the working surface, and grid
  or flex decides placement.

## Page-level commands

A page's one to three major commands (Create, Record, Issue, Import, Add, Set, Start, Request,
Book, Refresh, report downloads) use `PageAction` in the `PageHeader`: a square icon surface
(`size-12`) with the short label always visible below it. A command that navigates is a real link
(`PageActionLink`); one that acts or opens a dialog is a real button (`PageAction`, which forwards
its ref to a `DialogTrigger`). `labelDetail` completes the accessible name when the page makes the
object obvious ("Create" + "account"). `primary` is the page's main command; `secondary` the rest.
Commands wrap on narrow screens; they never collapse into unlabelled icons or a scrolling rail.

Ordinary `Button`s remain for Save, Cancel, Submit, Retry, Apply filters, dialog confirmations,
row actions, form navigation, destructive actions, and actions that belong to one region (Add
unavailability, Check worker). Back stays a text link. Record pages' own actions (Edit, PDF,
lifecycle actions) and Activity pages keep their current buttons.

## Maroon as structure

Maroon may mark structure, not only navigation and primary actions, with restraint:

* `border-brand-line` frames working surfaces, evenly on every side.
* `bg-brand-wash` with `text-brand-strong` marks table heads, and `PanelSection` headings use
  `text-brand`.
* Current and selected states.

Do not surround everything with dark maroon, put maroon backgrounds behind body text, or use maroon
or maroon-tinted text that fails contrast on the cream canvas. `brand-line` and `brand-wash` never
carry text contrast.

User decision: do not mark a panel, card, or region with a colored border on one side only — a
maroon (or any accent) top stripe or left stripe on a rounded container. It reads as a generic
AI-generated card. Emphasis comes from the content and its hierarchy, the panel's title band, and
the maroon section headings, not from an accent edge.

## Rules and dividers

A rule marks a real division, such as table rows, a list, or a panel's own sections. Do not use
heading → rule → content → rule as the default way to separate parts of a page; use a panel
boundary, a `PanelSection`, or spacing.

## Shared primitives

* `PageHeader` (`src/components/ui/page-header.tsx`): title, short description, back link, meta,
  and actions. Feature heading wrappers delegate to it.
* `Panel`, `PanelHeader`, `PanelBody`, `PanelSection`, `PanelFooter`, `PanelMessage`, and
  `RecordSummary` (`src/components/ui/panel.tsx`).
* `FloatingListTools`, `ListSearchField`, and `ListToolField`
  (`src/components/ui/floating-list-tools.tsx`, §47) for portal collections; `FilterToolbar` and
  `FilterField` (`src/components/ui/filter-toolbar.tsx`, §47) for public and in-flow filters.
* `pageSheetWidth` (`src/components/ui/page-width.ts`) for pages that are not collections (see
  Portal shell).
* `PageAction`, `PageActionLink`, and `PageActionGroup` (`src/components/ui/page-action.tsx`) for a
  page's major commands (see Page-level commands).
* `ActionStatus` (`src/components/ui/action-status.tsx`) for routine success (§53).
* `ContextHelp` (`src/components/ui/context-help.tsx`) for grouped page-level conceptual
  explanation; `Tooltip` for short control names and `IconAction` for named low-risk compact
  actions. Follow [the UI information hierarchy guideline](docs/ui-guidelines.md) (ADR-091).
* `dataTable` classes (`src/components/ui/data-table.ts`, §46).
* `describeResultPage` (`src/features/portal/components/result-context.ts`) for result context built
  only from canonical page facts.

Use these instead of feature-local wrappers or literal colors, radii, and borders. Add a shared
pattern only when it genuinely repeats.

## Page anatomy

Portal collection pages begin with their records. The page header is usually only the title and
the primary action; the search and filters float as the collection's tools (§47):

```text
PageHeader (title, primary action)
results Panel: PanelHeader with result context; table or list, and the
               loading, empty, and error states, inside the same panel
CanonicalPagination, with the results
FloatingListTools (out of the flow)
```

Public list pages keep `PageHeader`, then an in-flow `FilterToolbar`, then the results.

Dense tables keep their useful columns: a compact shell is not a reason to drop identity, status,
timestamps, or context, or to turn a table into cards.

Detail pages separate identity, status, facts, actions, and history:

```text
PageHeader
record Panel: RecordSummary (identity, status, key facts), then a PanelSection per detail group
separate Panels for actions and workflows
history and supporting information
```

Consequential actions never sit inside the informational groups.

Form pages present related fields as coherent task sections:

```text
PageHeader
one form sheet (Panel): a PanelSection per group, following the real
                        institutional form's grouping where one exists
PanelFooter: the one submit area
```

Do not wrap every pair of inputs in its own card. Controlled institutional wording keeps its own
approval; visual work adapts layout, not wording.

Live session workspaces, such as E-Counseling, depart from detail-page anatomy (ADR-093). The call
stage (the other participant, the self view, call state, what is being captured, and the call
controls) is the most prominent object; it sits beside the working area and stays in view with CSS
`sticky` while the work scrolls with the page. The two columns switch on at the workspace's own
width (a container query), so an expanded dock stacks them instead of squeezing them. Wide Counselor
workspaces offer named layout presets (Compact, Balanced, Focus), never a drag splitter; phones get
one adaptive layout with the call edge to edge and one row of call controls. Secondary work and
settled metadata collapse into disclosures with a visible one-line status; active capture, device
and connection problems, pending decisions and Leave never do. Keep one document scroll: no fixed
overlays and no nested scroll panes. Keep the call stage mounted at one place in the tree, so layout
changes only reflow it. The call is a Daily Call Object rendered by COMPASS; recording and
transcription start and stop only through the COMPASS backend.

Overview is the portal's home, not a dashboard. It greets the reader by name and gives today's date,
then puts what needs attention first, the reader's primary action (a `PageAction`) beside the greeting, and
announcements after the work. The summary counts are secondary context: one compact "At a glance"
list beside the work, never a row of metric tiles. It shows only what the Overview contract
returns. No metric-card grids, large icon plus number tiles, charts, trends, or dashboard filler,
and no character illustrations.

## Portal shell

Friendly shell, serious workspace. The frame around the work may be approachable: a responsive
dock, clear hover and focus feedback, a restrained expansion, a greeting on the Overview, and direct
human copy. The work itself stays sober: clean tables, plain record details, explicit sensitive
actions, no mascots, no playful wording around counseling, cases, privacy, or security, and no
ornamental motion around operational data.

* Navigation on wide screens is a dock in the brand color. It opens with its group and destination
  labels showing, and the reader can collapse it to an icon rail for more room with the icon button at
  the start of the top bar; the choice holds while they move between pages. In the rail, each icon
  shows its label on hover and keyboard focus. The current destination is a lit tile in the dock,
  not a stripe on one edge. Groups are separated by a line in the rail and named when expanded. On
  small screens the same destinations open in a drawer.
* The top bar is slim and holds the dock's collapse button, the account controls (Accessibility,
  notifications, account menu), and, on small screens, the drawer button and the COMPASS mark.
  COMPASS identity belongs to the dock; the top bar is not a second branded header.
* A current Privacy Notice that asks the reader for an acknowledgment opens one prompt over the
  workspace (`PrivacyNoticePrompt`), read from `my-notices?pending_acknowledgment=true`, one notice
  at a time. It never blocks work: "Not now" puts it off for the browser session, Account › Privacy
  keeps every notice, and it stays out of the Privacy page and live E-Counseling sessions.
  Acknowledgment is not consent, and the prompt says so.
* The shell gives every page the whole workspace, so collections can use it. A page that is not a
  collection — a record, a form, an editor, a page of running text — bounds itself with
  `pageSheetWidth`, and pages that share workspace tabs share one width. The Account workspace keeps
  its own narrower width. Never let running text span the workspace. Organization › Structure is
  read-only hierarchical text and bounds itself (`max-w-4xl`) while its sibling tabs keep the
  workspace for their tables.

## Maintenance Mode presentation

The public status (`/api/v1/platform/status`) decides what COMPASS shows, through
`useMaintenanceStatus` (`src/features/platform/maintenance-status.ts`):

* scheduled maintenance: a compact, non-blocking notice; COMPASS stays usable;
* active maintenance, public pages: a dedicated maintenance screen replaces the page;
* active maintenance, ordinary portal routes: the maintenance screen replaces the dock and
  workspace, so pages are not shown failing behind it;
* active maintenance, sign-in: stays usable, with a compact notice;
* active maintenance, Platform Operations: stays reachable for accounts that can use it, in a frame
  that depends only on APIs maintenance leaves available, so an operator can end maintenance.

Only a confirmed `maintenance_active` status locks a page; a status that could not be read never
does. A start or end time only prompts a fresh check — an expected end never unlocks COMPASS by
itself. Render the operator's message as plain text.

## Public pages

Public pages read like an active university information and service portal, not a startup landing
page. They use:

* a compact hero that introduces COMPASS rather than filling the first screen;
* useful content early: announcements, resources, and real service entry points;
* clearly bounded editorial regions.

Show only the services, links, and office details the application actually supports for the reader's
access state. Never invent contact details, office hours, or services. No feature grids or
marketing copy.

## Decoration

* Containers (panels, toolbars, framed messages) use `rounded-sm`; controls keep their own
  `rounded-md`. Keep `rounded-full` for compact statuses and tags.
* No one-sided accent borders on containers (see Maroon as structure).
* Shadows mark real layering only: dialogs, popovers, the skip link, and controls that float over
  the page. Dialogs and menus float with the dialog shadow and `rounded-md`; the floating list
  tools and the dock's labels use the lighter float shadow and `rounded-md`. Nothing on the page
  itself uses `rounded-lg` or larger.
* No gradients outside §18's branded surfaces.
* No glassmorphism, giant icons, colored icon circles, pills for everything, decorative metric
  cards, or empty-state illustrations.

## Typography

This grammar does not change typography (§15). Distinctiveness comes from structure, density,
institutional color, and hierarchy, not novelty fonts.

## V1 and V2

Archived frontends stay reference-only (§2). V1 informs information hierarchy, density, and service
visibility. V2 informs restrained maroon framing and moderate radius. Do not copy their code,
Bootstrap structures, navigation, yellow sign-in buttons, heavy shadows, tiny text, or accessibility
patterns.

## Review before handoff

Ask of every changed screen:

* Does it still look like generic AI/SaaS minimalism?
* Did whitespace simply turn into cards?
* Is maroon structural but restrained?
* Are related controls visibly related?
* Does useful information appear early?
* Is it denser without being cramped?
* Is it still accessible and responsive at phone width?

---

# 69. Final principle

COMPASS should feel like carefully designed institutional software.

Prefer:

```text
clarity
specificity
restraint
predictability
accessibility
real workflow semantics
```

over:

```text
decorative novelty
SaaS marketing patterns
AI-generated filler
visual noise
invented functionality
```

Every element—visual, interactive, or textual—must have a reason to exist.

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
