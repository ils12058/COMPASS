# Follow-ups and manual checks

## Separate page-content findings

The shell-focused fix leaves two enlarged-text findings in workspace content:

- At 320px / 200% root text on Student Home, the document is 328px wide while the header is exactly 320px. The `Announcements` heading has a 263px intrinsic text width inside a 190px content area, creating the 8px page spill. This belongs to the Overview Announcements panel in `fe/src/features/portal/home/overview-announcements.tsx`; changing that workspace content is outside this shared-shell slice.
- At 1024px / 200% root text on Student Inventory, document width is 1,223px while the header region is 512px wide and has no horizontal overflow. The remaining 199px spill comes from the narrow Inventory form area beside the expanded desktop dock. The Inventory workspace and form reflow are outside this slice.

These are real page-content reflow issues under enlarged root text and should be handled by their owning workspace/form follow-up. The 320px Student Inventory acceptance case itself has no page-wide horizontal overflow after this change.

## Manual verification still needed

- Test Safari with full keyboard navigation enabled to traverse every link and button using Tab; the local WebKit automation runner uses form-control-only Tab navigation by default.
- Test 200% browser zoom in current Chromium and Safari at narrow and desktop widths. The automated 200% root-font-size checks are not a substitute for browser zoom.
- Run screen-reader checks with VoiceOver and NVDA for skip-link announcement, accessible names, the native Accessibility popover, menu/dialog announcements, and focus return.
- Check on physical iOS and Android devices for touch behavior, safe-area spacing, and scrolling inside tall overlays.

Automated layout testing does not establish WCAG conformance. Proposal #15 remains experimental pending review and these manual checks.
