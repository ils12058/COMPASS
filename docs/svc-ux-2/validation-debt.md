# Validation debt

## Fixed-slot Inventory exception

SVC-UX-1 identified an Inventory-specific exception that can currently surface as HTTP 500 in the
fixed-slot Student booking path. This slice does not change Inventory eligibility, booking
semantics, or the backend error contract. It remains an explicit correctness follow-up for
SVC-UX-3, requiring a focused backend regression test and stable typed mapping.

## Feedback/CSM browser failures

The four SVC-UX-1 Feedback/CSM user-copy failures were not reproduced or attributed by this
frontend slice. They must be compared against baseline and integration before broad browser
results are called green; ownership remains with the SVC-UX-3 validation pass.

