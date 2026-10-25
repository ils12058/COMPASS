# Retirement impact and transactional blockers

GET `/{campuses|colleges|programs}/{target_id}/impact` requires current catalog management authority.
Its strict response contains target_id, resource_version, observed_at, can_deactivate, typed
blockers/warnings, fixed aggregate count fields and preserved historical categories. No names,
Student IDs, Inventory answers, message bodies, Counseling contents or dependent-record examples
are included. Each count uses its own FK/subquery predicate; no to-many join multiplies rows.

| Count categories | Actual relationship |
|---|---|
| child/active Colleges | Campus FK; zero for other target types |
| descendant/active Programs | College FK under target Campus/College; zero child count for Program |
| all/active Student/inactive-account affiliations | StudentAffiliation College FK; active Student role across every supported lifecycle |
| Counselor responsibilities | Every responsibility row, including inactive or stale Counselor assignment |
| draft/submitted Inventories | Program FK; submitted_at determines retained submission versus draft |
| Graduate Tracer | graduated_college OR graduated_program FK, one count per response |
| open Office/resolved threads | Saved routing_college FK, never handler identity or name matching |
| pending Good Moral/pending F4/issued | Linked Inventory Program OR affected current affiliation Student subquery; snapshots alone do not establish a catalog FK |
| pending operational Follow-Ups | Student's current College affiliation and OPERATIONAL/PENDING fields; no confidential description hydration |

Program has no StudentAffiliation FK. Its affiliation/responsibility/thread counts are zero; do not
pretend Inventory Program proves Guidance placement. Campus/College Good Moral counts are a bounded
indirect impact population and can include a request through either source; OR prevents double
counting. F6 without linked Inventory/current affiliation cannot be reliably attributed by saved
degree/College text and is deliberately not name-matched. Historical issued snapshots remain safe.

Hard blockers:

- Campus: active child Colleges; active Student affiliations or any responsibility below even if an
  already-inconsistent inactive child hides them; open Office work and pending operational Follow-Ups.
- College: active child Programs; any active Student-role affiliation; any responsibility row;
  open Office threads and pending operational Follow-Ups that depend on the retiring scope.
- Program: submitted history alone never blocks. Draft Inventory and pending Good Moral are warnings;
  selection/submission validates active ancestry after retirement.

The actual lifecycle enum is CURRENT / GRADUATED / FORMER. The prompt's GRADUATING / ALUMNI names
are not stored values; no new lifecycle values/policy are invented. The blocker filters active
STUDENT role without restricting lifecycle, covering all supported values.

Warning codes are inactive_account_affiliations, draft_inventories and pending_good_moral. Resolved
threads, submitted Inventories, issued certificates, Tracer references and inactive affiliations
are preserved categories, not automatic retirement blockers. No automatic child cascade,
affiliation removal, responsibility removal or reassignment occurs.

Office handler assignment never grants access: current staff scope excludes inactive Colleges.
Open Office retirement therefore fails closed until the owning workflow resolves/remediates it.
Resolved rows remain saved; existing scope-based staff history can become unavailable after
retirement. This slice does not grant new historical message access. Confidential Follow-Up/source
ownership remains independent; operational pending work conservatively requires explicit remediation.
Institutional workflow-retirement and historical-view decisions remain activation gates.

A preview does not reserve state and a target version cannot detect newly inserted dependencies.
The status service takes the exclusive gate, locks/rechecks target/version and recomputes impact;
`catalog_deactivation_blocked` includes safe blocker code/count details. Client `can_deactivate`
fields are rejected. Independent-connection stale-preview/assignment tests prove transactional
reassessment. Account reactivation checks retained affiliation/responsibility ancestry under the
shared gate and returns existing `organization_relationship_conflict`; explicit repair is required.
