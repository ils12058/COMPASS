# SIMPLIFY-3B — Caveat and the public hero

Baseline: `4bfc1b4185c46cff2a40598f071bad1f2e40168e`, fetched 29 October 2026. This is a limited design prototype for review, not approval to apply script typography to the whole product.

The user clarified that the desired handwritten face is Caveat, already used on the public hero. The same existing font definition is scoped to the Student Overview greeting, an expressive display heading; the title text and semantic heading remain the same. Outfit remains the functional heading face, including the staff and administrative Home headings. Script is not applied to controls, small labels, records, forms or critical instructions. The font remains `next/font` self-hosted in the browser; the public layout and Student Home share the existing font configuration.

The prior hero sentence is replaced by “A place to talk and find support.” The underlying title, rotation, pause behavior, links and meaning of available services are unchanged. The hero's grid child can now shrink and its text can wrap at enlarged text instead of clipping; its action controls can wrap.

## Synthetic previews

| Surface | Before | After |
| --- | --- | --- |
| Student Home, 390px | [Before](screenshots/before-student-390.png) | [After](screenshots/after-student-390.png) |
| Student Home, 1440px | [Before](screenshots/before-student-1440.png) | [After](screenshots/after-student-1440.png) |
| Public hero wording | Earlier copy: “You don’t have to find your way alone.” | [390px](screenshots/hero-390.png) · [1440px](screenshots/hero-1440.png) |

Chromium and WebKit each passed 10/10 Student, Counselor and GSS Home checks, 5/5 hero checks and 3/3 reduced-motion/forced-colors checks. These cover 320–1440px, 200% root text, a long synthetic name, unchanged non-Student heading fonts, hero rotation and the reduced-motion default. Focused ESLint, typecheck and a webpack production build passed. Synthetic fixtures and browser emulation do not prove physical-device, real-screen-reader, live-service or institutional UAT coverage. The public shell's separately verified narrow-width enlarged-text overflow is outside this slice.
