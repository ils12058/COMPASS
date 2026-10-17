# COMPASS-UX-P1 Implementation Report

## Delivery

- PR: [#273 — feat(fe): refine portal experience (UX-P1)](https://github.com/ils12058/COMPASS/pull/273), targeting `staging`.
- Implementation source commit: `ea103d9f78522e6d29e059fe14700b4c3c950204`.
- Base: `staging` at `59b4c2f1` (EC-FIX-1). The UX-P1 commit was rebased onto this base without conflicts.
- Status: open for review; not merged or deployed.

## Changes

- The desktop portal dock keeps its flat left edge and uses an 8px radius on the visible right corners. Expanded and collapsed navigation, badges, focus tips, and the square mobile drawer remain supported.
- Appointment and Referral detail views reuse `PageAction` and `PageActionGroup` for 48px square icon surfaces with visible labels. Actions sit in a contextual desktop rail and stay near the heading on mobile. The appointment reference and status lead the page; secondary operational dates and unavailable-action reasons have lighter hierarchy. Referral sections keep their existing record meaning and history while reducing redundant borders.
- The global header mute control is removed. Account Preferences now contains “In-app pop-up alerts” with the requested description and “Show pop-up alerts” checkbox. The setting defaults to enabled, persists in local storage per signed-in account, and synchronizes immediately between the settings page and the single global presenter. It controls in-app pop-ups only; the bell, unread count, Notification Center, email, and browser-push settings are unchanged. Existing active-call, hidden-tab, and blocking-dialog suppression remains in place.

## Components and files

Reused components include `PageAction`, `PageActionGroup`, `PageHeader`, `RecordSummary`, `DisclosureSection`, `Panel`, and the existing `BrowserPushControls` Notifications panel. The only new shared preference module is `notification-heads-up-preference.ts`, which provides the account-scoped local setting to both consumers.

Implementation changes are in `fe/src/components/ui/page-action.tsx`; the portal shell/navigation; Appointment and Referral detail/shared components; and Account Preferences plus the notification presenter and BrowserPush panel. Regression coverage is in the updated portal, page-action, navigation, Messages, consistency, and realtime browser tests, with new notification-preference unit tests and `fe/tests/ux-p1.browser.mjs`.

No backend, API contract, database, authorization, generated client, or eCounseling workspace files are included in this PR.

## Visual evidence

All screenshots use synthetic fixtures.

| View | Before | After |
|---|---|---|
| Desktop expanded navigation | [Before](fe/docs/ux-p1-visuals/before/portal-desktop-expanded.png) | [After](fe/docs/ux-p1-visuals/after/portal-desktop-expanded.png) |
| Desktop collapsed navigation | [Before](fe/docs/ux-p1-visuals/before/portal-desktop-collapsed.png) | [After](fe/docs/ux-p1-visuals/after/portal-desktop-collapsed.png) |
| Mobile navigation | [Before](fe/docs/ux-p1-visuals/before/portal-mobile-drawer.png) | [After](fe/docs/ux-p1-visuals/after/portal-mobile-drawer.png) |
| Appointment desktop | [Before](fe/docs/ux-p1-visuals/before/appointment-desktop.png) | [After](fe/docs/ux-p1-visuals/after/appointment-desktop.png) |
| Appointment mobile | [Before](fe/docs/ux-p1-visuals/before/appointment-mobile.png) | [After](fe/docs/ux-p1-visuals/after/appointment-mobile.png) |
| Appointment with Messages open | [Before](fe/docs/ux-p1-visuals/before/appointment-messages-open.png) | [After](fe/docs/ux-p1-visuals/after/appointment-messages-open.png) |
| Referral desktop | [Before](fe/docs/ux-p1-visuals/before/referral-desktop.png) | [After](fe/docs/ux-p1-visuals/after/referral-desktop.png) |
| Referral mobile | [Before](fe/docs/ux-p1-visuals/before/referral-mobile.png) | [After](fe/docs/ux-p1-visuals/after/referral-mobile.png) |

The preference placement is shown in [Account Preferences](fe/docs/ux-p1-visuals/after/account-notification-preferences.png).

## Validation and findings

- `pnpm test`: 816/816 passed.
- `pnpm lint`, `pnpm typecheck`, and `pnpm build`: passed.
- UX-P1 Appointment/Referral browser checks: 16/16 Chromium and 16/16 WebKit.
- Contextual Messages: 29/29 in both browsers; notification realtime and preference: 12/12 in both browsers.
- Portal navigation: 3/3 in both browsers; frontend consistency: 46/46 in both browsers; UX hardening: 60/60 in both browsers; Appointment reminders: 3/3 in both browsers.
- Layout checks cover 320px through 1440px, including tablet and wide desktop. They passed without horizontal overflow. Action groups keep visible labels, links/buttons retain their semantics, and the narrow Messages drawer retains Escape and focus-return behavior.

## Limits and next candidates

The pop-up preference is specific to this browser/device and signed-in account; it does not sync to other devices. Browser push delivery itself was not changed.

For a later portal-wide pass, audit Call Slip and Service detail pages for suitable page-level actions, then review list/filter density and navigation spacing at narrow phone widths. These candidates were not implemented here.
