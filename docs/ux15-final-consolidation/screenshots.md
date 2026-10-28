# Screenshot and Geometry Evidence Index

The final consolidation did not duplicate the existing screenshots or the temporary test-run
artifacts. The links below point to committed synthetic evidence from the corresponding merged
UX15 slices. These images document the implementation scenarios and are not stakeholder UAT or
live-system captures. The final rerun's detailed results were written under the local temporary
directory by the existing harness and were not copied into the repository.

| Surface | Representative evidence | Geometry/results |
| --- | --- | --- |
| Student Home and 320px enlarged announcements | [Mobile pending Home](../ux15-home-1/screenshots/after/ux15-student-home/after-mobile-pending.png), [Announcements 320px/200%](../ux15-home-1/screenshots/after/ux15-student-home/after-announcements-320-200-detail.png) | [Student Home geometry](../ux15-home-1/screenshots/after/ux15-student-home/geometry.json), [browser results](../ux15-home-1/screenshots/after/ux15-student-home/results.json) |
| Counselor and Head Home | [Agenda and work](../ux15-home-2/screenshots/after/chromium/ux15-counselor-home/after-counselor-desktop-agenda-work.png), [Head without optional capabilities](../ux15-home-2/screenshots/after/chromium/ux15-counselor-home/after-head-without-optional-capabilities.png) | [Counselor geometry](../ux15-home-2/screenshots/after/chromium/ux15-counselor-home/geometry.json), [browser results](../ux15-home-2/screenshots/after/chromium/ux15-counselor-home/results.json) |
| GSS Home | [Managed schedule](../ux15-home-3/screenshots/after/chromium/ux15-gss-home/after-gss-desktop-managed-appointments.png), [320px/200% root text](../ux15-home-3/screenshots/after/chromium/ux15-gss-home/after-gss-320-200-text.png), [restricted capabilities](../ux15-home-3/screenshots/after/chromium/ux15-gss-home/after-gss-restricted-capabilities.png) | [GSS geometry](../ux15-home-3/screenshots/after/chromium/ux15-gss-home/geometry.json), [browser results](../ux15-home-3/screenshots/after/chromium/ux15-gss-home/results.json) |
| Inventory reflow and submission recovery | [Expanded dock, 1024px/200% editable](../ux15-hardening-1/screenshots/inventory-after-1024-200-expanded-editable.png), [committed response/lost response](../ux15-hardening-1/screenshots/after-routine-committed-response-lost.png) | [Inventory geometry](../ux15-hardening-1/screenshots/inventory-after-geometry.json), [hardening validation](../ux15-hardening-1/validation.md) |
| Exit Interview | [Phone conditional error](../ux15-exit-interview/screenshots/after-phone-conditional-error.png), [phone review](../ux15-exit-interview/screenshots/after-phone-ready.png) | [Exit Interview screenshot index](../ux15-exit-interview/screenshots.md), [validation](../ux15-exit-interview/validation.md) |
| Graduate Tracer | [Phone matrix](../ux15-graduate-tracer/screenshots/after-phone-matrix.png), [saved phone draft](../ux15-graduate-tracer/screenshots/after-phone-saved.png) | [Tracer screenshot index](../ux15-graduate-tracer/screenshots.md), [validation](../ux15-graduate-tracer/validation.md) |
| Counselor Evaluation | [Finalized view](../ux15-counselor-evaluation/screenshots/after-finalized.png), [finalization confirmation](../ux15-counselor-evaluation/screenshots/after-finalization-confirmation.png) | [Evaluation screenshot index](../ux15-counselor-evaluation/screenshots.md), [validation](../ux15-counselor-evaluation/validation.md) |
| Routine Intake | [Section navigation](../ux15-routine-intake/screenshots/after-phone-section-navigation.png), [submitted read-only](../ux15-routine-intake/screenshots/after-read-only-submitted.png) | [Intake screenshot index](../ux15-routine-intake/screenshots.md), [validation](../ux15-routine-intake/validation.md) |
| Customer Feedback and CSM | [Customer uncertain status](../ux15-hardening-1/screenshots/after-customer-uncertain.png), [CSM same-key retry](../ux15-hardening-1/screenshots/after-csm-unsubmitted-same-key-retry.png) | [Hardening validation](../ux15-hardening-1/validation.md), [Feedback/CSM screenshot index](../ux15-feedback-csm/screenshots.md) |
| Shared form layout/accessibility matrix | [Audit findings and reproduction notes](../ux15-consolidation-1/accessibility-audit.md) | [Per-engine geometry and validation record](../ux15-consolidation-1/validation.md) |
| Portal Shell, dialogs, menu, and navigation | [Accessibility audit](../ux15-accessibility-1/accessibility-validation.md) | [Shell validation and limitations](../ux15-accessibility-1/validation.md) |

The form and Home suites use synthetic API fixtures. Root-font enlargement in the geometry files
is not browser zoom. See [accessibility audit](accessibility-final-audit.md) for the manual checks
still required.
