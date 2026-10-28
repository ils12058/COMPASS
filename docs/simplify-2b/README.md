# COMPASS-SIMPLIFY-2B — 3D illustration collection

The collection contains the four approved GCO character artworks and ten complementary feature
illustrations. All production files are real transparent PNGs under
[`fe/public/illustrations/`](../../fe/public/illustrations/). The first three objects are reused,
not duplicated. No additional character poses were justified by a planned placement.

![Complete collection](contact-sheet.png)

## Assets and optimization

| Filename | Dimensions | PNG size |
| --- | --- | --- |
| `gco-character-point-right.png` | 512 × 512 | 179.1 KiB |
| `gco-character-point-up.png` | 512 × 512 | 173.6 KiB |
| `gco-character-wave.png` | 512 × 512 | 165.9 KiB |
| `gco-characters.png` | 1024 × 512 | 492.3 KiB |
| `appointment-calendar-3d.png` | 512 × 512 | 178.8 KiB |
| `service-catalog-3d.png` | 512 × 512 | 179.4 KiB |
| `guidance-messages-3d.png` | 512 × 512 | 128.5 KiB |
| `individual-inventory-3d.png` | 512 × 512 | 202.1 KiB |
| `counseling-3d.png` | 512 × 512 | 108.3 KiB |
| `guidance-followups-3d.png` | 512 × 512 | 153.7 KiB |
| `good-moral-3d.png` | 512 × 512 | 179.9 KiB |
| `exit-interview-3d.png` | 512 × 512 | 112.8 KiB |
| `graduate-tracer-3d.png` | 512 × 512 | 155.4 KiB |
| `announcements-3d.png` | 512 × 512 | 142.1 KiB |

All 14 PNGs total **2,613,011 bytes (2.49 MiB)**, 83.9% smaller than the recovered/generated
high-resolution source PNGs. Character exports alone drop from 5,058,379 to 1,035,100 bytes
(79.5%). The approved source artwork is unchanged: production exports use uniform downsampling
and transparent-pixel cleanup, with no character regeneration, pose changes or redesign.
Existing character filenames are preserved; duplicate `gco-*-3d` aliases are not shipped.

The 1024px group supports its current maximum 304px-wide slot at 2x density. The 512px individuals
support the 96px title-band slots, and 512px feature objects support the recommended 96–224px
placements at 1x/2x densities. Existing `next/image` handles responsive optimized delivery;
separate WebP source variants are unnecessary. All figures/objects have clear padding and retain
their aspect ratio. Counseling deliberately retains two separate chairs and a separate bubble.

## Sources and visual review

Approved full-resolution character inputs remain in the original local workspace at
`/Users/reynantlntno/Projects/COMPASS/fe/public/illustrations/`. They are 1408 × 1408 for the three
individuals and 2048 × 1024 for the group. Their verified SHA-256 hashes and every final export
hash are recorded in [asset-manifest.json](asset-manifest.json).

The ten raw object PNGs were generated with the built-in image_gen tool using the approved
characters as the definitive style reference. Raw generator files remain in
`/Users/reynantlntno/.codex/generated_images/01a180ce-89e6-7fd1-991e-282fd5f464eb/`;
the manifest lists their individual source filenames, hashes, dimensions and byte counts.
[generation-prompts.json](generation-prompts.json) records the exact prompt set.
The user authorized pixel processing for export-fringe cleanup, padding and the contact sheet.
[prepare-assets.py](prepare-assets.py) is the one-off preparation script, not an application service.
High-resolution sources stay outside this PR to avoid shipping redundant asset variants.

The contact sheet was inspected on cream and dark backgrounds for cohesive materials, lighting,
camera/scale, recognizable silhouettes, clean edges and absence of baked backgrounds or text.
Legitimate maroon clothing, folders, ribbons and object details remain. Decorative perimeter
strokes, background scribbles and export debris are removed. No new clinical symbols, official
seals, personal data or status claims appear.

## Public integration and 2C handoff

The public landing group now reserves the correct 2:1 aspect ratio. Announcements and Resources
use the correct square intrinsic dimensions; `PublicPageHeader` declares its 96px rendered size
so the image optimizer does not request an unnecessarily large source. Title-band artwork stays
hidden below 640px. Existing layout, image paths, empty alt text and non-focusable behavior remain.

The branch is based on merged SIMPLIFY-2A (`843e96eb`). **No role-based Home component changed.**
The [SIMPLIFY-2C placement map](placement-map.md) identifies real target components, benefits,
decorative/informative treatment, display sizes, priorities and exclusion boundaries. The
guidelines narrowly permit useful object accents; they do not authorize illustration on every
screen, replace Lucide controls, or decorate confidential work, tables or consequential dialogs.
Routine Interview and Reports assets were deliberately deferred; the map explains why.

## Verification and limits

- Client generation, lint, typecheck and production build passed on the rebased branch:
  [frontend-validation.txt](checks/frontend-validation.txt).
- Public search and browser-discovery regressions: **19/19 passed**:
  [focused-tests.txt](checks/focused-tests.txt).
- Chromium and WebKit: **10/10 each**, including nine actual public-page renders at 1440, 390
  and 320px widths, delayed image loading, stable reserved image/heading geometry (within 1px),
  aspect ratios, empty alt text, no image focus stops, no heading/control overlap, horizontal
  containment and successful decoding of all 14 production paths:
  [Chromium log](checks/chromium.txt), [WebKit log](checks/webkit.txt).
- [Nine Chromium screenshots and results](screenshots/chromium/public-illustrations/) include
  [landing desktop](screenshots/chromium/public-illustrations/landing-desktop.png),
  [Announcements desktop](screenshots/chromium/public-illustrations/announcements-desktop.png),
  [Resources phone](screenshots/chromium/public-illustrations/resources-phone.png), and
  [320px landing](screenshots/chromium/public-illustrations/landing-narrowPhone.png).
  [WebKit results](screenshots/webkit/results.json) record the second-engine checks.
- Image checks verify alpha extrema 0/255, padding, expected separate silhouettes and per-file
  size budgets; source and output hashes are in the manifest. Brand marks, logo files, color
  tokens, backend, contracts, authorization and 2A-owned Home paths have no diff.

Browser evidence uses a local production build with synthetic API fixtures; it is not live-service
or institutional UAT evidence. Screenshots are 1x; 2x sizing is supported by the source-resolution
budget, not a physical-device claim. Manual screen-reader and live-device checks were not run.
Feature objects are prepared for 2C and are not yet imported into portal screens. No merge or
deployment is included.
