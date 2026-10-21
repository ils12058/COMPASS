# Visual evidence

All views use synthetic Student accounts and completed-service opportunities in the local browser
harness. Before captures come from the unmodified `integration/ux15-modernization` source baseline
`a4c8bed349e0a7e774f8a6bde3bb805fb0168543`; after captures use the pilot build. Paired beginning
and questionnaire views use the same 1440×1000 desktop or 390×844 phone viewport. The screenshots
show the portal shell and are viewport captures, not full-page captures.

## Customer Feedback

| View | Before | After |
| --- | --- | --- |
| Desktop beginning | [Before desktop beginning](screenshots/before-customer-desktop-beginning.png) | [After desktop beginning](screenshots/after-customer-desktop-beginning.png) |
| Phone beginning | [Before phone beginning](screenshots/before-customer-phone-beginning.png) | [After phone beginning](screenshots/after-customer-phone-beginning.png) |
| Desktop rating questions | [Before desktop ratings](screenshots/before-customer-desktop-ratings.png) | [After desktop ratings](screenshots/after-customer-desktop-ratings.png) |
| Phone rating questions | — | [After phone ratings](screenshots/after-customer-phone-ratings.png) |
| Respondent information, optional fields blank | — | [After respondent information](screenshots/after-customer-respondent-information.png) |
| Native required-field focus | — | [After validation focus](screenshots/after-customer-validation-focus.png) |
| Submission confirmation | — | [After confirmation](screenshots/after-customer-confirmation.png) |
| Uncertain submission and same-response retry | — | [After uncertain result](screenshots/after-customer-uncertain.png) |
| Confirmed success | — | [After success](screenshots/after-customer-success.png) |

## Client Satisfaction Measurement

| View | Before | After |
| --- | --- | --- |
| Desktop beginning | [Before desktop beginning](screenshots/before-csm-desktop-beginning.png) | [After desktop beginning](screenshots/after-csm-desktop-beginning.png) |
| Phone beginning | [Before phone beginning](screenshots/before-csm-phone-beginning.png) | [After phone beginning](screenshots/after-csm-phone-beginning.png) |
| CC1 answer 4 — CC2/CC3 N/A | [Before N/A branch](screenshots/before-csm-charter-not-applicable.png) | [After N/A branch](screenshots/after-csm-charter-not-applicable.png) |
| Phone SQD ratings | [Before phone ratings](screenshots/before-csm-phone-ratings.png) | [After phone ratings](screenshots/after-csm-phone-ratings.png) |
| Required-field focus | — | [After validation focus](screenshots/after-csm-validation-focus.png) |
| Invalid optional email | — | [After email validation](screenshots/after-csm-email-validation.png) |
| Submission confirmation | — | [After confirmation](screenshots/after-csm-confirmation.png) |
| Uncertain submission and same-response retry | — | [After uncertain result](screenshots/after-csm-uncertain.png) |
| Confirmed success | — | [After success](screenshots/after-csm-success.png) |

Visual inspection found and corrected duplicate uncertain-result messaging: the warning and its
retry action now occupy one shared notice in each form. Native validation focus, conditional fields,
CC1’s N/A representation, radio selection, mobile wrapping and success states were also inspected.
At 320px with 200% text, browser assertions cover each modified form’s reflow; the surrounding
portal shell has a known separate top-bar overflow at that setting. See [validation.md](validation.md)
for that limitation and the manual checks that remain pending.
