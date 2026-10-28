# History and cross-domain compatibility

Fixed-slot booking continues to create the canonical Appointment and keeps its slot booking provenance; a booked/withdrawn slot retains its linked Appointment rather than deleting history. Group registration, attendance, event cancellation, and facilitator history remain in Group Sessions. Flexible appointments retain their snapshots, reference code, status, and normal management lifecycle.

The selected Appointment, fixed-slot, Group Session, scheduling-consequence, and notification-link tests passed. Those suites include access-denial and historical-state assertions. Existing SVC-UX-1 tests verify links to the current Appointment/session and avoid fabricated identities after ambiguous results.

No SVC-UX-3 changes touch Inventory, Routine Interviews, Counseling Encounters, E-Counseling, messages, or notification delivery. Booking does not grant confidential-record access. Group attendance does not create an individual Encounter. External SMTP/provider delivery and live notification delivery were not exercised; local notification/deep-link behavior is not proof of delivery.
