# Synthetic screenshot and geometry index

All captures use local synthetic Student/session/API fixtures. They contain no live Student data. The baseline captures replay the audited pre-fix Inventory layout; `inventory-before-geometry.json` preserves the original unmodified-source measurement as well as the responsible elements.

## Inventory matched views

- 1024px / 200% / expanded dock, editable: `screenshots/inventory-before-1024-200-expanded-editable.png` and `screenshots/inventory-after-1024-200-expanded-editable.png`.
- 1024px / 200% / collapsed dock, editable: `screenshots/inventory-before-1024-200-collapsed-editable.png` and `screenshots/inventory-after-1024-200-collapsed-editable.png`.
- Submitted/read-only views at 1024px / 200%, expanded and collapsed dock: `screenshots/inventory-after-1024-200-expanded-read-only.png` and `screenshots/inventory-after-1024-200-collapsed-read-only.png`.
- 320px / 200% editable: `screenshots/inventory-before-320-200-editable.png` and `screenshots/inventory-after-320-200-editable.png`.
- 390px / 100% editable: `screenshots/inventory-before-390-normal-editable.png` and `screenshots/inventory-after-390-normal-editable.png`.
- 1440px / 100% / expanded dock editable: `screenshots/inventory-before-1440-normal-expanded-editable.png` and `screenshots/inventory-after-1440-normal-expanded-editable.png`.
- Complete measurements: `screenshots/inventory-before-geometry.json` and `screenshots/inventory-after-geometry.json`.

## Recovery states

- Routine Intake: `screenshots/after-routine-committed-response-lost.png`, `screenshots/after-routine-canonical-submitted-conflict.png`, and `screenshots/after-routine-status-unavailable-preserved.png`.
- Customer Feedback: `screenshots/after-customer-uncertain.png`, `screenshots/after-customer-status-unavailable.png`, and `screenshots/after-customer-already-submitted-after-lost-response.png`.
- CSM: `screenshots/after-csm-uncertain.png` and `screenshots/after-csm-unsubmitted-same-key-retry.png`.
- Normal and confirmation states for both instruments are also captured in this directory.

The screenshots show UI states; the automated browser test results in [validation](validation.md) establish which synthetic scenarios passed.
