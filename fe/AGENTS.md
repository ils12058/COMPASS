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

User-approved exception: on the maroon public footer, `public/brand/ucn-logo.png` may be rendered
in solid white with a CSS filter (`brightness-0 invert`), because the maroon mark is not visible on
that background. This does not permit recoloring brand marks anywhere else.

Character illustrations are appropriate primarily for public-facing, onboarding, empty-state, or friendly informational contexts where they genuinely support the message. They should normally not appear inside dense administrative workspaces.

Current placements: the group image in the public landing hero; the waving character at sign-in;
the pointing-up character in the public Announcements title band and on the not-found page; and
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
→ close
→ invalidate/refresh affected data
→ provide appropriate feedback
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

## Filter toolbar

The search and filter controls for one list form one `FilterToolbar`
(`src/components/ui/filter-toolbar.tsx`) between the page header and the results, so they read as
one tool rather than inputs placed on the page. Label each control with `FilterField`. Do not add a
large "Filters" heading when the controls already say what they do.

Every control in a toolbar applies the same way:

* explicit: one form, one `Apply filters` submit, and Enter in the search field submits the same
  form. This is the default when a free-text search sits beside other filters.
* immediate: each change applies. Use it for a toolbar of a few selects or dates without free-text
  search, or for a lone debounced directory search.

Do not give the search field its own Search button while neighboring filters apply on change. Show
`Clear filters` in the toolbar's action area only while a filter is active. A toolbar that holds a
text search sits in a form with `role="search"` and an accessible name.

A long toolbar folds its secondary filters away. When a text search sits beside more than two other
filters, pass the others as `advanced`: the search, a `Filters` button, and the actions share one
row, and the advanced filters open below it. The button counts the advanced filters in use
(`advancedCount`, from the applied results, counting a filter only when it differs from its
default), and the section starts open while any is in use so the reader can see what narrows the
results. Folded fields stay in the form. Toolbars with no text search, or with one or two filters
beside it, stay fully visible. Messages about how filters were applied stay outside the folded
section.

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

# 53. Toasts and transient feedback

Do not make toasts the only place where important failures are communicated.

Use inline/contextual errors for forms and consequential workflows.

Toasts may supplement clear state changes.

Do not produce a toast after every trivial action merely because a toast component exists.

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

Do not create sidebar pages merely because separate API endpoints exist.

The portal sidebar and the public landing's quick access read one access list,
`portalWorkspaceGroups` (`src/features/portal/components/portal-workspaces.ts`). It orders the
sidebar by how often the work happens: scheduling, records, requests and surveys, content, and
reports first; institution setup, identity and access, privacy governance, and platform operations
last. Add a workspace there, in the group where its daily use belongs.

Information architecture is product design, not an automatic projection of the backend router.

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
* `FilterToolbar` and `FilterField` (`src/components/ui/filter-toolbar.tsx`, §47).
* `dataTable` classes (`src/components/ui/data-table.ts`, §46).
* `describeResultPage` (`src/features/portal/components/result-context.ts`) for result context built
  only from canonical page facts.

Use these instead of feature-local wrappers or literal colors, radii, and borders. Add a shared
pattern only when it genuinely repeats.

## Page anatomy

List pages separate page purpose, tools, result context, and records:

```text
PageHeader
FilterToolbar
results Panel: PanelHeader with result context; table or list, and the
               loading, empty, and error states, inside the same panel
CanonicalPagination
```

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

Overview stays task-first: bounded regions for what needs attention, the summary, announcements,
and upcoming work only when real records exist. No metric-card grids, large icon plus number tiles,
or dashboard filler.

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
* Shadows mark real layering only: dialogs, popovers, the skip link. Dialogs and menus float with
  the dialog shadow and `rounded-md`; nothing on the page itself uses `rounded-lg` or larger.
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
