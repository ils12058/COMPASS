# SIMPLIFY-3B — public shell at enlarged text

Baseline: `4bfc1b4185c46cff2a40598f071bad1f2e40168e` on `integration/ux15-modernization`. At 320px with 200% root text, the synthetic public Privacy page had a 400px scroll width: the brand and menu extended beyond the viewport and the footer forced words into an excessively narrow column.

The public header now responds to its available container width and wraps when needed. The narrowest presentation retains the COMPASS mark and accessible home link while omitting the adjacent UCN mark from the header; the unmodified UCN asset remains in the footer. The account menu and public navigation remain available for signed-in readers, and the mobile menu follows its trigger when the header wraps. The footer stacks its institutional identity where a side-by-side layout is too narrow.

Accessibility settings move from the floating public control into the header so they do not obscure page content. The confirmed maintenance screen retains its own accessibility control; its heading wraps at enlarged text. No authentication or maintenance state logic changes.

[Before](screenshots/before-public-320-enlarged.png) and [after](screenshots/after-public-320-enlarged.png) use synthetic data at 320px and 200% root text. Chromium and WebKit each passed 21/21 public shell and maintenance checks, 13/13 existing public-illustration checks, and the targeted portal account-menu check. The 13 maintenance unit checks, focused ESLint, TypeScript and a webpack production build passed. These are local browser fixtures, not physical-device, real-screen-reader, authenticated-production or institutional UAT evidence. The wider SIMPLIFY-3 route and role audit remains incomplete.
