# Privacy and access boundaries

## GSS and Counselor separation

- GSS Home uses the GSS role branch. Student Home and Counselor/Head Home keep their own branches; IT Admin and other professional roles keep the existing shared Overview.
- GSS schedule reads use `appointmentsListManaged` only when the current account has `appointments.manage`. The Home never uses `/appointments/me` for GSS.
- The backend managed-list service scopes records by current actor authority and operational responsibility. A frontend capability enables useful presentation only; the backend remains authoritative for every list and detail read.
- The schedule preview uses the list contract's Student, provider, Service, date, status, and delivery-mode fields. It does not render appointment purpose or counseling content.
- Routine Interview evaluation tasks and aggregate metrics remain hidden from GSS by the existing Counselor-only access helper, even if a shared schema is populated unexpectedly.

## Good Moral separation of duties

- Preparation work appears only when the existing `getGoodMoralAccess(user).canPrepare` predicate permits it.
- A Good Moral issuance work item is not rendered as an issuance command for GSS. Where an operational viewer can open the request, the Home labels it as awaiting Counselor issuance and offers only “View request.”
- Aggregate issuance counts are labeled as waiting for Counselor issuance, have no transaction link, and remain office context rather than a GSS assignment.
- Home never prepares or issues a certificate.

## Messages, Call Slips, Follow-Ups, and destinations

The Home reuses current message, Call Slip, Follow-Up, Good Moral, and general workspace access helpers. It does not infer create/manage authority from a visible aggregate. Every destination comes from `portalWorkspaceGroups(user)`, which itself uses the current workspace-level policy. Backend ownership and resource scope remain unchanged.

Group Session, Referral, Availability, and Service destinations appear only if the existing workspace projection includes them. Home does not enumerate a scope, broaden a route, or create a shortcut to a mutation.

## Negative checks

The synthetic suites verify that:

- no managed schedule request occurs without `appointments.manage`;
- GSS never requests the self-Appointment endpoint;
- cancellation and next-day fixtures are excluded by the managed API's scheduled/today filters;
- private purpose fixture text is absent from rendered and accessible content;
- Counselor evaluations and Good Moral issuance are not presented as GSS final actions;
- null metrics are omitted and zero metrics remain zero;
- transient failures preserve only last-confirmed data, while authorization failures do not reuse it;
- switching from a GSS account to a Student account removes the GSS work and managed schedule destinations.

The API and domain tests remain responsible for proving server-side scope, assignment, College, supervision, and direct-resource authorization. Browser tests are not a substitute for those enforcement tests or institutional UAT.
