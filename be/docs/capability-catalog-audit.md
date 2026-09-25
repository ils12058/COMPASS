# Capability catalog audit — 2026-09-25

This is a review of all 67 canonical definitions in `compass/accounts/policy.py` at the staging baseline. Names and full descriptions live in that policy file. The table records each definition, its baseline grant source, direct backend consumers, direct frontend checks, authority class, and rename decision. A dash means no direct literal-code consumer; generic access inspection and capability resolution still enumerate all canonical definitions. Frontend paths are audit evidence only; this backend PR does not edit `fe/`.

Role abbreviations: IT = IT Admin, C = Counselor, GSS = Guidance Services Staff, S = Student, IO = Institutional Officer. Head and DPO are designations layered on compatible roles. Backend consumer names are modules under `be/compass/`; frontend names are features under `fe/src/features/`.

| Capability | Name | Class | Baseline grant | Backend direct consumer | Frontend direct check | Decision |
|---|---|---|---|---|---|---|
| `accounts.view` | View account identity | Reference/discovery | IT, C, GSS, S | — | — | Retained |
| `accounts.manage` | Manage accounts | Management/configuration | IT | account_management, authentication | accounts, portal | Retained |
| `institutional_designations.manage` | Manage institutional designations | Management/configuration | IT | account_management | accounts | Retained |
| `platform_operations.view` | View platform operations | Reporting/oversight | IT | overview, platform_ops | platform, portal | Retained |
| `platform_operations.manage` | Manage platform operations | Management/configuration | IT | platform_ops | platform | Retained |
| `privacy_governance.view` | View privacy governance | Reporting/oversight | DPO | privacy_governance | — | Retained |
| `privacy_governance.manage` | Manage privacy governance | Management/configuration | DPO | privacy_governance | — | Retained |
| `organization.structure.view` | View organizational structure | Reference/discovery | IT, C, GSS, S | organization | institution-configuration, inventory, organization | Renamed in place |
| `organization.manage` | Manage organization | Management/configuration | IT, Head | organization | institution-configuration, organization | Retained |
| `academic_years.view` | View academic years | Reference/discovery | C, Head | organization | institution-configuration, inventory | Retained |
| `academic_years.manage` | Manage academic years | Management/configuration | Head | organization | institution-configuration | Retained |
| `institutional_forms.view` | View institutional form metadata | Reference/discovery | C, Head | institutional_forms | institution-configuration | Retained |
| `institutional_forms.manage` | Manage institutional form metadata | Management/configuration | Head | institutional_forms | institution-configuration | Retained |
| `services.catalog.view` | View service catalog | Reference/discovery | IT, C, GSS, S | service_catalog | portal, services | Renamed in place |
| `services.manage` | Manage service catalog | Management/configuration | IT, Head | service_catalog | services | Retained |
| `availability.view` | View availability | Mixed; split deferred | IT, C, GSS, S | availability | availability | Retained; split design needed |
| `availability.manage` | Manage availability | Management/configuration | IT, Head | availability | availability | Retained |
| `availability.manage_self` | Manage own availability | Self-service | C | availability | availability | Retained |
| `appointments.view_self` | View own appointments | Self-service | C, GSS, S | appointments | appointments | Retained |
| `appointments.manage_self` | Manage own appointments | Self-service | S | appointments | appointments | Retained |
| `appointments.manage` | Manage appointments | Scoped operational | C, GSS, Head | appointments | appointments | Retained |
| `counseling.view_assigned` | View assigned counseling encounters | Scoped operational | C | counseling | counseling | Retained |
| `counseling.manage_assigned` | Manage assigned counseling encounters | Scoped operational | C | counseling | counseling | Retained |
| `shared_summaries.view_self` | View own shared counseling summaries | Self-service | S | counseling | counseling | Retained |
| `shared_summaries.view_assigned` | View assigned shared counseling summaries | Scoped operational | C | counseling | counseling | Retained |
| `shared_summaries.manage_assigned` | Manage assigned shared counseling summaries | Scoped operational | C | counseling | counseling | Retained |
| `inventory.view_self` | View own individual inventory | Self-service | S | inventory | inventory | Retained |
| `inventory.manage_self` | Manage own individual inventory | Self-service | S | inventory | inventory | Retained |
| `inventory.view` | View submitted individual inventories | Scoped operational | C | inventory | inventory | Retained |
| `inventory.reopen` | Reopen individual inventories | Scoped operational | C | inventory | inventory | Retained |
| `student_support.view` | View Student Support context | Scoped operational | C | student_support | — | Retained |
| `reports.view` | View aggregate reports | Reporting/oversight | C, Head | reports | reports | Retained |
| `exit_interviews.view_self` | View own Exit Interviews | Self-service | S | exit_interviews | exit-interviews | Retained |
| `exit_interviews.manage_self` | Manage own Exit Interview | Self-service | S | exit_interviews | exit-interviews | Retained |
| `exit_interviews.view` | View Exit Interviews | Reporting/oversight | Head | exit_interviews | exit-interviews | Retained |
| `exit_interviews.reopen` | Reopen Exit Interviews | Reporting/oversight | Head | exit_interviews | exit-interviews | Retained |
| `routine_interviews.view_self` | View own routine interviews | Self-service | S | routine_interviews | routine-interviews | Retained |
| `routine_interviews.manage_self` | Manage own routine interview intake | Self-service | S | routine_interviews | routine-interviews | Retained |
| `routine_interviews.view_assigned` | View assigned routine interviews | Scoped operational | C | routine_interviews | routine-interviews | Retained |
| `routine_interviews.manage_assigned` | Manage assigned routine interviews | Scoped operational | C | routine_interviews | routine-interviews | Retained |
| `referrals.view` | View scoped referrals | Scoped operational | C, GSS | referrals | referrals | Retained |
| `referrals.manage` | Manage scoped referrals | Scoped operational | C, GSS | referrals | referrals | Retained |
| `call_slips.view` | View scoped Call Slips | Scoped operational | C, GSS | call_slips | call-slips | Retained |
| `call_slips.manage` | Manage scoped Call Slips | Scoped operational | C, GSS | call_slips | call-slips | Retained |
| `call_slips.view_self` | View own Call Slips | Self-service | S | call_slips | call-slips | Retained |
| `good_moral.view_self` | View own Good Moral requests | Self-service | S | good_moral | good-moral | Retained |
| `good_moral.request_self` | Request own Good Moral certificate | Self-service | S | good_moral | good-moral | Retained |
| `good_moral.view` | View Good Moral requests | Scoped operational | C | good_moral | good-moral | Retained |
| `good_moral.manage` | Manage Good Moral requests | Scoped operational | C | good_moral | good-moral | Retained |
| `good_moral.issue` | Issue Good Moral certificates | Scoped operational | C | good_moral | good-moral | Retained |
| `feedback.submit_customer_feedback` | Submit Customer Feedback | Self-service | S | feedback | feedback | Retained |
| `feedback.view_customer_feedback` | View Customer Feedback | Reporting/oversight | Head | feedback | feedback | Retained |
| `feedback.submit_csm` | Submit Client Satisfaction Measurement | Self-service | S | feedback | feedback | Retained |
| `feedback.view_csm` | View Client Satisfaction Measurement | Reporting/oversight | Head | feedback | feedback | Retained |
| `graduate_tracer.view_self` | View own Graduate Tracer response | Self-service | S | graduate_tracer | graduate-tracer | Retained |
| `graduate_tracer.manage_self` | Manage own Graduate Tracer response | Self-service | S | graduate_tracer | graduate-tracer | Retained |
| `graduate_tracer.view` | View Graduate Tracer responses | Reporting/oversight | Head | graduate_tracer | graduate-tracer | Retained |
| `document_branding.view` | View document branding | Management/configuration | Head | documents | — | Retained |
| `document_branding.manage` | Manage document branding | Management/configuration | Head | documents | — | Retained |
| `announcements.manage` | Manage GCO announcements | Management/configuration | C, GSS | announcements | — | Retained |
| `resources.manage` | Manage curated GCO resources | Management/configuration | C, GSS | resources | — | Retained |
| `ecounseling.view_self` | View own E-Counseling workspace | Self-service | S | ecounseling | ecounseling | Retained |
| `ecounseling.join_self` | Join own E-Counseling session | Self-service | S | ecounseling | ecounseling | Retained |
| `ecounseling.consent_self` | Decide own E-Counseling media consent | Self-service | S | ecounseling | ecounseling | Retained |
| `ecounseling.view_assigned` | View assigned E-Counseling workspace | Scoped operational | C | ecounseling | ecounseling | Retained |
| `ecounseling.join_assigned` | Join assigned E-Counseling session | Scoped operational | C | ecounseling | ecounseling | Retained |
| `ecounseling.manage_media_assigned` | Manage assigned E-Counseling media | Scoped operational | C | ecounseling | ecounseling | Retained |

## Semantic decisions

| Legacy/current code | Decision | New code | Evidence and migration effect |
|---|---|---|---|
| `organization.view` | Rename in place | `organization.structure.view` | Only six Campus, College, and Program list/get routes use this read guard. Responsibility, supervision, affiliation, people picker, and mutations require `organization.manage`. Student, GSS, Counselor, and IT grants remain; Head inherits Counselor read and has designation management. Frontend currently uses the broad code to show the Organization workspace. |
| `services.view` | Rename in place | `services.catalog.view` | Active Service list/get are the guarded reads. Inactive list additionally requires `services.manage`; inactive retrieve is hidden without management; mutations require management and recent MFA. Student, GSS, Counselor, and IT grants remain; Head inherits Counselor read and has designation management. Frontend currently uses the broad code to show the Services workspace. |
| `availability.view` | Retain; split deferred | — | It guards both effective provider windows for scheduling and Counselor self Availability reads (with a role check). One legacy GRANT or REVOKE cannot be mapped to separate effective and self capabilities without choosing new authority or losing intended access. Frontend has operational Availability checks; an explicit override design is needed before any split. |
| `academic_years.view` | Retain | — | The only direct guard lists all Academic Year labels/current flags; Counselor inventory and report filters consume that reference. The same read can support a read-only year screen, while `academic_years.manage` alone guards creation/current-year selection. A rename would change overrides without clarifying a distinct backend authority class. Frontend uses this read for both filters and an institution configuration affordance; the latter needs frontend composition review. |
| `institutional_forms.view` | Retain | — | Its definition already says form metadata, and its only guards list Form Families and revisions. Counselors need controlled-form metadata; `institutional_forms.manage` separately guards registration/activation. Whether the frontend should show a standalone read-only metadata screen is a product affordance decision, not an additional backend authority. |
| `accounts.view` | Retain | — | Its definition is scoped account identity projection, but no route or service directly tests this code today. Account Management uses `accounts.manage`; other domains apply their own guards and scope to person projections. Renaming or removing this dormant baseline would change persisted override intent without fixing a reachable access path. |

## Boundary review

The remaining 61 definitions have action-specific names or are bounded by self, assigned, scoped operational, management/configuration, or oversight guards. Direct backend consumers are listed above. Cross-domain use of reference data includes Student booking through Service and effective Availability lookup, Program selection in Inventory, Academic Year filters in Inventory and reports, and controlled-form metadata in document workflows. These consumers do not gain management authority from the two renamed reads. All baseline role/designation grant sets and route scope/state checks stay the same.

`Capability` remains a scope-free action class. Role/designation gives actor identity and baseline grants; routes/services enforce record scope, lifecycle eligibility, and recent MFA. A frontend workspace is a composition of usable actions, not a capability code. Unknown or legacy codes are filtered by `CAPABILITY_CODES` and receive no runtime alias.
