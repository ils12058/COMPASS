# Frontend UX hardening validation

Staging base: `80f43c471ea0ac318c7da3ebcc116ec747d5825b` (fetched October 9, 2026).
Branch: `codex/frontend-ux-hardening`. This is a frontend-only slice targeting `staging`.

## Revalidation before implementation

The older audit was not treated as authoritative. Source inspection, synthetic API fixtures and
browser probes reproduced the current defects. The initial browser endpoint belonged to another
local worktree; its HEAD was verified to equal the exact staging base and its working tree was
clean. Dedicated server ports were subsequently used for the implementation and an untouched
staging archive. Baseline widths and deterministic races were reconfirmed against that clean base.

Baseline `api:generate`, unit tests (351), lint, typecheck and production build passed.
The existing hierarchy browser suite reproduced its intermittent Call Slip tooltip failure
(13/14 checks); the preceding draft/session suite passed 20/20.

| Finding | Current staging classification | Evidence | Correction and principal files |
| --- | --- | --- | --- |
| UX-001 | STILL PRESENT | Inventory and Exit responses enlarge the document; non-sticky hidden sort descriptions use an outer containing block | `relative` on the existing sort button and a bounded native-control action row, `src/components/ui/sortable-column-header.tsx` / `panel.tsx` |
| UX-002 | STILL PRESENT | Typing commits search, fetches and disconnects the focused input | Explicit Search/Enter, stable local draft, URL acknowledgement/history ownership, `src/features/accounts/list/accounts-list.tsx` |
| UX-003 | STILL PRESENT | Services and Affiliations Clear is undone by the previous draft/debounce | Parent owns draft and Clear, cancels timers and distinguishes navigation acknowledgements; Services list/shared and Student Affiliations page |
| UX-004 | STILL PRESENT | Hold a completed `Mar` navigation, type `Maria`, release: baseline finishes at `Mar` | Track issued searches and preserve newer draft; `src/features/availability/availability-pages.tsx` |
| UX-005 | CHANGED / PARTLY ALREADY FIXED | Announcement title already fits; PageHeader email, Service code/list and Referral URL overflow | Description/code wrapping, zero-minimum mobile grid tracks; PageHeader, Services list/detail, Referral detail |
| UX-006 | STILL PRESENT | Accepted long email makes sticky identity approximately 1304px wide | Fixed rem-based inner content width and wrapping; Accounts list |
| UX-007 | STILL PRESENT | Native siblings exist but lack the shared current-view visual treatment and wrapping | Existing WorkspaceTabs/workspaceTabClass; Exit workspace page |
| UX-008 | CHANGED / PARTLY ALREADY FIXED | Responses/Student access siblings and access heading already correct; queue/opportunity wording, missing context and ambiguous empty state remain | Responses/access copy, existing result context, distinct empty states and GSS sidebar label; touched Exit components and portal workspace labels |

No whole finding was already completely fixed. Already correct Announcement title containment,
sibling labels and capability/destination rules were preserved. No product decision remained.

## Interaction behavior

Accounts previously searched after 350ms and remounted its keyed input. It now updates only a local
draft during typing. Search or Enter trims and applies that draft to the existing `search` URL
parameter, resets pagination to page 1 and preserves structured filters and ordering. Submissions
create history entries; Back/Forward and reload restore the committed search. A delayed submission
acknowledgement cannot replace text typed after submission. Clear removes search and relevant
filters, keeps ordering and clears the draft. Pagination uses the applied query even while newer
text remains unsubmitted.

Services and Student Affiliations remain live. Their collection components own both the draft and
Clear, cancel the timer immediately, and record self-issued search values before navigation. An
older acknowledgement advances the applied query without replacing newer typing. Unknown URL
changes and deliberate Back/Forward adopt the URL. Availability uses the same local ownership rule
and retains live search and pagination. No global store or search framework was introduced; other
Organization searches retain their existing behavior.

## Width and accepted-content evidence

Chromium baseline, with a 393px `documentElement.clientWidth`:

| Case | Baseline document scrollWidth | Fixed scrollWidth |
| --- | ---: | ---: |
| Inventory | 881 | 393 |
| Exit Interview responses | 605 | 393 |
| PageHeader description, 173-character valid email | 1500 | 393 |
| Service detail, 120-character name and accepted 64-character code | 478 | 393 |
| Referral detail, 260-character URL/token | 2100 | 393 |
| Announcement, 120-character unbroken title | 393 | 393 (already contained) |

The collection regression covers Inventory, Exit responses, Resources and Accounts (unaffected by
the sort-description defect) at 320, 375, 390, 393, 430, 768 and 1440px in Chromium and WebKit. It
asserts `documentElement.scrollWidth <= documentElement.clientWidth + 1`, at both horizontal ends,
checks the sticky identity position, local table scrolling, accessible sort state and usable
Filters dialogs. Table minimum widths and the hidden description/aria-sort remain intact. No
html/body overflow hiding was added.

Accepted-content checks additionally cover the Service list at 393 and 1440px. The shared header
case replaces only the text in its actual rendered description. Full authoritative text remains
visible and wrapping; no new truncation or global typography reduction was used.

Accounts tests cover short identity, the valid long email, a 50-character Institutional ID and a
120-character display name. Identity content is bounded to 12rem on phones and 16rem on wider
screens. The sticky column remains useful while later columns remain exposed at the far end.
At 393px, the long-email sticky cell falls from 1303.8px to 230.4px inside a 359px scrollport;
the Accounts table falls from 1668px intrinsic width to its unchanged 704px minimum. Inventory
retains its 1008px local table width and Exit responses retain 744px: page containment does not
come from shrinking those tables.

Later Accounts columns currently contain plain text: the keyboard/pointer geometry regression
inserts a synthetic input in the final cell to prove reachability without introducing UX-012's
keyboard redesign into the product.

## Exit workspace

Sibling navigation retains native links, aria-current, exact destinations and capability gating.
The active sibling uses existing WorkspaceTabs styling and wraps responsively. Responses replace
queue wording in the collection and return links. Access wording replaces ordinary UI opportunity
wording in the panel, loading/caption/pagination, dialogs, opening helper and GSS sidebar. Backend
names, capabilities, operation IDs, enums and the `workspace=opportunities` URL stay unchanged.

The access panel derives current-page result context only from existing canonical page facts.
Empty states distinguish no access records, no matching records and an empty later page. Authorized
Open access remains visible. Student access and access-only/response-only capability cases retain
their current authorization behavior.

## Regression implementation and validation

- `tests/ux-hardening.browser.mjs`: 56 scenario checks per engine, covering the above widths,
  accepted content, sticky geometry, explicit search, live Clear, controlled navigation races,
  history, Exit sibling/copy and capability visibility.
- `tests/support/ux-hardening-fixtures.mjs`: synthetic records and canonical collection responses.
- `tests/support/browser-harness.mjs`: configurable Chromium/WebKit and viewport, clientWidth
  assertion, per-suite artifacts, and blocked service workers. Worker-owned fetches otherwise
  bypass Playwright routing; blocking workers keeps synthetic API fixtures isolated in both engines.
- `tests/portal-command-palette.test.mjs`: GSS access wording with unchanged workspace visibility.
- `test:ui:ux` runs both engines. `test:ui` and targeted `test:ui:regressions` include it.
- `frontend-targeted.yml` installs both browsers and warms the new routes before timing checks.

API generation passes: all 702 generated files match the untouched staging generation byte for
byte. `contracts/openapi.json`, backend files and generated client sources were not changed.

Final unit tests: 352 passed. Lint, typecheck and production build passed. Typecheck and build ran
sequentially. A first full browser run hit a cold-route compilation timeout; routes were warmed
before the required rerun, matching the targeted CI approach.

Final focused browser suite: Chromium **56/56**, WebKit **56/56** (112 checks).
The warmed full `pnpm test:ui` run passed draft/session **20/20**, then failed only the existing
Call Slip `icon-tooltip-interaction` check in the hierarchy suite (**13/14**), matching clean
staging. The remaining existing suites were run separately: E-Counseling call **31/31** and
runtime **17/17**. This is not a green full `test:ui` baseline.

The first targeted CI run passed units/build and Chromium 56/56 but found one Linux WebKit
Resources failure at 320px: the native Sort select widened the document to 327px. A counterfactual
reproduced 326px locally with the measured 256px select width; allowing PanelHeader's existing
actions row to shrink restored 320px. This additional directly affected shared-component correction
is covered by the Resources 320px case in both engines. Targeted CI installs/runs both engines
through `test:ui:regressions`; consult the PR checks for its latest remote execution result. Browser output includes per-engine result JSON, mobile screenshots
and clientWidth/table/sticky measurements under the configured artifact directory.

## Deferred backlog

UX-009 temporary read-state alignment; UX-010 WebKit pointer focus return; UX-011 named search
landmarks; UX-012 dense table keyboard-pan redesign; UX-013 wording outside this bounded slice.
Realtime, Guidance Messages, backend/API/authorization changes and unrelated flows remain outside
this PR. No merge or deployment is part of this implementation.
