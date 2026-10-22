# Individual Inventory constrained-content reflow

## Reproduced cause

The pre-fix browser measurement reproduces the documented 1024px viewport, 200% root text, expanded dock failure. The document scroll width was **1223px** while the viewport was **1024px**. The main/header region was 512px; the Inventory editor/workspace had only 384px. Its viewport-triggered two-column layout still reserved a 416px navigation rail plus a 48px gap, leaving a **2px** panel. Controls and text in that panel extended beyond the viewport. The cause was the Inventory content's fixed minimum navigation column in a workspace narrowed by the dock, not the Portal Shell header.

The source capture in `screenshots/inventory-before-geometry.json` records offending Inventory fields and buttons beyond the 1024px viewport. The browser test can replay the old layout against current markup to capture before screenshots; the original 1223px measurement was recorded from the unmodified source.

## Correction

Inventory now lays out its section navigation beside the panel only when its own named workspace container is at least 42rem wide. In a narrower workspace, navigation becomes the existing native section selector and the panel takes the full workspace. This covers enlarged root text even when the viewport itself is desktop-sized. Existing field container queries remain in place. No `overflow-x-hidden`, clipped content, reduced font or touch size, viewport JavaScript, questionnaire edits, or payload changes were introduced.

## Measurements

At 1024px/200% with the expanded dock, the document changed from **1223px** to **1024px**. The main region remains 512px; the Inventory workspace remains 384px. Before, the nav occupied 416px and the panel only 2px; after, both nav selector and panel fit the full 384px workspace. The panel no longer protrudes and the measured offender list is empty.

At 1024px/200% with the collapsed dock, the document is 1024px both before and after; the panel was 280px next to the 416px rail before, and the full-width 744px workspace is used after. At 320, 360, 390, 768, 1024, and 1440px, both 100% and 200% root text sizes were checked. Editable and submitted/read-only views were checked at 1024px/200% with expanded and collapsed dock states. Captures include 320px/200%, 390px/100%, and 1440px/100%; see [screenshots](screenshots.md) and the complete geometry JSON.

## Verification and remaining checks

The focused Inventory suite passed 13/13 checks in Chromium and 13/13 in WebKit after the final layout change. It checks whole-document overflow, each section's content, save/submit/review behavior, section jumps, keyboard focus, and navigation safeguards. This uses 200% root-font enlargement; it is not browser zoom. Manual browser zoom, screen-reader, physical-device, and institutional task checks remain open in [follow-ups](followups.md).
