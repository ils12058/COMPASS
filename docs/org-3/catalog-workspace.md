# Catalog workspace

`fe/src/features/organization/structure/organization-structure-page.tsx` composes the existing
hierarchy and adjacent bounded `catalog/` components. No route was added. Existing relationship
routes gained their own `OrganizationRelationshipsGate` because the outer workspace now also
admits eligible reference readers and Catalog-only managers.

| Actor | Structure | Catalog actions | Responsibilities / Student affiliations |
|---|---|---|---|
| Eligible staff + structure view + Catalog manage | Yes | Yes | Only with organization.manage |
| Existing relationship manager + structure view | Yes | Only with explicit Catalog manage | Existing access |
| Eligible staff + structure view alone | Read-only | None | None |
| Student with reference reads | No standalone workspace | None | No new authority |
| Unsupported role with malformed Catalog grant | No Catalog entry from that grant | None | Existing independent authority only |

Eligible technical roles mirror ORG-2: IT Admin, Counselor and Guidance Services Staff. Role alone
never grants editing. Institution navigation, the dock and Go-to use the same entry helpers;
relationship commands/tabs are omitted unless independently authorized. Direct navigation to a
relationship route is gated before its component can make requests. Staff Supervision remains
inside Responsibilities, with its original capability and MFA semantics.

Each Campus remains a Panel. Colleges are rows; Programs are indented beneath the College.
Identity, code, status, actual classification and Year Level policy stay visible. Contextual
`Actions` disclosures expose Add College/Program, Rename, policy (Program), history and status only
to Catalog managers. Add Campus uses PageAction. Longer editing tasks use one inline form sheet;
the hierarchy remains available below it, with other mutations unavailable during that intent.

Search and status/Campus/College filters operate on the complete returned unpaginated collections.
One Search/Enter applies all controls together. No invented paging, caps, remote parameters or
polling are added. Descendant matches keep their actual ancestors, labeled Parent context when the
parent itself is outside the query/status. A matching ancestor's descendants remain constrained by
status. Empty filtered child groups explicitly say no children match these filters. Clear filters
returns the full hierarchy. Existing relationship live search remains unchanged.

After a confirmed save and successful refresh, browsing narrows to the saved record's Campus and,
where relevant, College, clearing search/status so a new inactive record is visible. Other filters
stay local to this workspace. Closing an editor restores its opener or the shared focusable page
heading when that opener is gone. Reopening does not reuse another intent's form.

Configured `[1,3,5]` displays `1st, 3rd and 5th Year`; only an actually contiguous set becomes a range.
Null classification and pending levels have explicit pending labels. Nothing reads degree names
as academic policy. Inactive records remain available for reference browsing.
