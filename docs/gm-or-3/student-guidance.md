# Student guidance and privacy

Pending self-service F4 and F6 request detail now includes four next steps:

1. Pay the applicable certificate fee at UCN Cashier and confirm its amount with Cashier/GCO.
2. Keep the physical Official Receipt, using a separate receipt for each certificate request.
3. Present it at the Guidance and Counseling Office for processing.
4. Return to COMPASS to check this request's status.

The current Student-safe response contains no approved expected-fee decision. Therefore the UI does **not** advertise PHP 80 as approved, infer a date range or expose staff policy evidence. The team-reported PHP 80 practice remains documented in earlier slices, not an invented Student pricing response. COMPASS does not accept online payments or independently confirm Cashier records.

Creation forms and mutation payloads are unchanged: no OR number/date/amount, inspection, upload or payment field is added. F4 retains Inventory/classification, year level, Exit Interview and CURRENT lifecycle rules. F6 retains its degree/date claim and clear verification limitation. Successful creation still navigates to the existing owned detail where next steps appear. Assisted initiation and notifications retain their established behavior.

Student components read only the existing Student-safe generated operations. They never request the operational inspection/history endpoints or display inspector references, grant data, ledger mode, internal mutation/reconciliation records or another Student's claim. Existing own saved receipt fields remain readable where the safe response already provides them; no invented Student receipt-state API exists.

ISSUED detail retains the original authorized PDF/download component and issuer/form metadata. No new receipt/fee/inspection prerequisite is added to historical download. Pending guidance is absent on issued/cancelled records, preventing a second-payment instruction for a completed certificate.
