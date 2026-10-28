# Synthetic visual evidence

Before: production build of exact integration
`757eb933786b8067724394c365d3a760279a1627`. After: production build of this consolidation.
All API responses are intercepted locally with synthetic records. Both sides use the same fixture,
fonts, viewport and named destination. No live Student or Counselor content was used.

Only three representative pairs are needed; existing pilot inventories remain the baseline for
unchanged forms. The new browser test's optional capture mode reproduces these destinations.

| Correction | Viewport/text | Before | After |
| --- | --- | --- | --- |
| Inventory family choice targets | 320×1000, default text; Mother works overseas label centered | [Before](screenshots/before-inventory-320.png) | [After](screenshots/after-inventory-320.png) |
| Exit Interview checkbox targets | 390×1000, default text; significant learning group | [Before](screenshots/before-exit-390.png) | [After](screenshots/after-exit-390.png) |
| Evaluation panel wrapping | 320×1000, 200% root text; Adjustment ratings heading | [Before](screenshots/before-evaluation-320-200.png) | [After](screenshots/after-evaluation-320-200.png) |

The uncorrected global shell has one diagnostic capture, without a before/after claim:
[Portal header at 320px/200% text](screenshots/after-portal-header-320-200.png).

Emergency wrapping at 200% can break a long word across lines so all of it remains inside the
sheet; it does not alter the stored or official string. Choice-label spacing increases only
where the baseline target was smaller. Captures are inspected alongside actual geometry tests,
since a screenshot does not establish target size or complete sheet reflow.

The shell overflow is intentionally retained and documented separately in the accessibility audit;
no content is clipped or hidden to make a whole-page check appear to pass. Existing inventories:
[Inventory](../ux15-pilot/README.md), [Exit](../ux15-exit-interview/screenshots.md),
[Tracer](../ux15-graduate-tracer/screenshots.md), [Intake](../ux15-routine-intake/screenshots.md),
[Evaluation](../ux15-counselor-evaluation/screenshots.md),
[Customer Feedback/CSM](../ux15-feedback-csm/screenshots.md).
