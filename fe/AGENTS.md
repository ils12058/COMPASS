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

The only automatically preserved visual identity from the prior frontend is the approved palette and typography documented below.

Everything else must earn its place in the new implementation.

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

* purple/blue gradient aesthetics;
* decorative gradients of any color;
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

* whitespace;
* hierarchy;
* borders;
* dividers;
* tables;
* lists;
* sections;
* tabs

when they communicate structure better.

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

Do not add bounce, spring, hover-lift, or continuous animation merely to make the interface feel modern.

---

# 45. Icons

Use Lucide icons consistently where icons improve comprehension.

Icons are not decoration quotas.

Do not add an icon to every heading.

Critical actions require text labels unless a universally understood icon has a proper accessible label and the context makes the action unambiguous.

---

# 46. Tables and operational lists

When users need to compare multiple structured records, prefer tables or deliberate lists.

Do not turn dense administrative data into a wall of oversized cards.

Lists must account for:

* loading;
* empty;
* error;
* filtering;
* pagination;
* row actions;
* keyboard/accessibility behavior.

Use stable backend pagination contracts.

Do not invent a total count if the API does not provide one.

---

# 47. Search and filters

Use backend-supported parameters only.

Do not fabricate client-side global search over paginated server data and present it as complete.

Keep shareable/list-navigation state in URL search parameters when doing so materially improves navigation and return behavior.

Do not add filters merely because a field exists in a response.

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

# 68. Table and list selection

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

## Row actions

Use a dedicated actions column only when rows genuinely have multiple contextual actions.

Prefer:

* clicking the primary record link or title to open detail;
* one clearly visible primary row action when appropriate;
* an overflow menu for secondary actions.

Do not place five to eight full-size buttons in every row.

Consequential row actions still require the standard confirmation flow.

## Row selection

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

Preserve search and filter state while moving between pages.

Reset to page 1 when a filter or search change invalidates the current page.

## Empty results

Differentiate between:

* no records existing;
* no records matching the current filters or search.

For a filtered empty state, provide a clear way to clear or adjust filters.

Do not show a celebratory empty state for routine administrative data.

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
