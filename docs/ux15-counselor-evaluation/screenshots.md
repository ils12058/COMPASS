# Before and after

All captures use the same synthetic Counselor, Student, Evaluation values, and Encounter records. Before captures come from the fetched `c5f1bb2b` integration baseline; after captures come from the final production build. Desktop uses 1440×1000 and phone uses 390×844. Rating, narrative, dirty, and saved views use equivalent interactions.

| View | Before | After |
| --- | --- | --- |
| Desktop beginning | ![Before desktop beginning](screenshots/before-desktop-beginning.png) | ![After desktop beginning](screenshots/after-desktop-beginning.png) |
| Phone beginning | ![Before phone beginning](screenshots/before-phone-beginning.png) | ![After phone beginning](screenshots/after-phone-beginning.png) |
| Desktop ratings | ![Before desktop ratings](screenshots/before-desktop-ratings.png) | ![After desktop ratings](screenshots/after-desktop-ratings.png) |
| Phone ratings | ![Before phone ratings](screenshots/before-phone-ratings.png) | ![After phone ratings](screenshots/after-phone-ratings.png) |
| Desktop narrative fields | ![Before desktop narrative fields](screenshots/before-desktop-narrative.png) | ![After desktop narrative fields](screenshots/after-desktop-narrative.png) |
| Phone narrative fields | ![Before phone narrative fields](screenshots/before-phone-narrative.png) | ![After phone narrative fields](screenshots/after-phone-narrative.png) |
| Desktop unsaved draft | ![Before desktop unsaved draft](screenshots/before-desktop-unsaved.png) | ![After desktop unsaved draft](screenshots/after-desktop-unsaved.png) |
| Phone unsaved draft | ![Before phone unsaved draft](screenshots/before-phone-unsaved.png) | ![After phone unsaved draft](screenshots/after-phone-unsaved.png) |
| Desktop confirmed save | ![Before desktop confirmed save](screenshots/before-desktop-saved.png) | ![After desktop confirmed save](screenshots/after-desktop-saved.png) |
| Phone confirmed save | ![Before phone confirmed save](screenshots/before-phone-saved.png) | ![After phone confirmed save](screenshots/after-phone-saved.png) |
| Encounter already linked | ![Before linked Encounter](screenshots/before-linked.png) | ![After linked Encounter](screenshots/after-linked.png) |
| Direct Encounter selected and ready | ![Before direct Encounter selection](screenshots/before-direct-selection.png) | ![After direct Encounter selection](screenshots/after-direct-selection.png) |
| No eligible Encounter | ![Before no eligible Encounter](screenshots/before-no-eligible-encounter.png) | ![After no eligible Encounter](screenshots/after-no-eligible-encounter.png) |
| Finalization confirmation | ![Before finalization confirmation](screenshots/before-finalization-confirmation.png) | ![After finalization confirmation](screenshots/after-finalization-confirmation.png) |
| Finalized read-only Evaluation | ![Before finalized Evaluation](screenshots/before-finalized.png) | ![After finalized Evaluation](screenshots/after-finalized.png) |

Visual review found the after layout separates adjustment ratings, narrative observations, save progress, and finalization without duplicating card frames. The rating scale is explained once and remains programmatically attached to each radio group. On mobile the controls wrap and the finalization section follows the editable Evaluation. The screenshots demonstrate presentation only; they do not imply institutional approval.
