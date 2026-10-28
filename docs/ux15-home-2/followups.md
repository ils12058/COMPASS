# Follow-ups

- Run Counselor and Head Guidance Counselor UAT with the Guidance Office and GCO before treating this experimental Proposal #15 work as accepted.
- Complete manual screen-reader, keyboard, focus, reduced-motion, actual browser-zoom, and physical mobile touch checks. Automated browser geometry is not a conformance claim.
- Plan the separate UX15-HOME-3 slice for Guidance Services Staff/GOA operational Home. Do not fold it into this PR or rename backend roles based on the GOA terminology proposal.
- Consider additional Head operational aggregate projections only in a separately reviewed proposal with explicit source definitions, authorization policy, and privacy review. This implementation adds no staff-wide or clinical aggregate.
- Reassess whether professional continuation links should be reordered after observing real Counselor workflows; current selection is permission-filtered and capped, not an empirically ranked usage report.
- Keep the canonical Work Queue and Appointment resource endpoints as the operational truth; future improvements should extend their domain-owned read contracts instead of aggregating Home-specific records.

No case-continuity, cross-Counselor record sharing, new Counseling lifecycle, Evaluation workflow, Follow-Up subsystem, or new management permission is introduced here.
