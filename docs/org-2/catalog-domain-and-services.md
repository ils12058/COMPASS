# Catalog domain and protected services

[catalog_services.py](../../be/compass/organization/catalog_services.py) is separate from existing
relationship management. Public create/rename/status/policy entry points require a saved actor,
persisted server AuthSession, matching AuditContext and bounded change basis. They reload authority
inside the transaction. There is no system/seed bypass for ordinary catalog management.

| Operation | Inputs and behavior |
|---|---|
| create_campus | Code, official name, explicit initial active state, basis; global code identity |
| create_college | Campus UUID plus creation fields; active child requires active Campus |
| create_program | College UUID plus creation fields and complete coherent policy; active creation requires full active ancestry and configured known policy |
| rename_campus / rename_college / rename_program | Target UUID, expected_resource_version, new name, basis; UUID/code/parent unchanged |
| set_campus_active / set_college_active / set_program_active | Explicit Boolean, target/version/basis; fresh dependencies or active ancestry/policy validated |
| update_program_policy | Complete classification/status/levels plus target/version/basis; shared ORG-1 validator |
| get_catalog_impact | Authorized target/model; advisory aggregate retirement and policy context |
| get_catalog_history | Authorized target/model; bounded page, page_size 1–50; safe attributable changes |

Codes use existing `normalize_code` (trim and uppercase), then require `[A-Z0-9][A-Z0-9_-]{0,31}`.
New codes cannot contain internal spaces or punctuation outside hyphen/underscore. Existing codes
are not rewritten. Uniqueness remains global for Campus and parent-qualified for College/Program;
duplicate normalized creation returns `catalog_duplicate_code`. The same code beneath another
parent denotes a different institutional identity. An inactive identity still reserves its code.

Names and basis are stripped nonblank Unicode plain text, at most 160 characters after stripping;
Unicode control/format/surrogate/private/unassigned characters are rejected. Names need not be
unique. Unicode institutional names are preserved, without case folding or invented transliteration.
An identical stripped name is a no-op, including adopted names with outer whitespace.
Validated updates write only changed columns; model save hooks cannot normalize unchanged adopted
identity/name values in the returned object or fabricate Audit differences. No-op state/policy updates retain version, updated_at and Audit.
A stale expected version fails even if the proposed value happens to equal the current value.

Ordinary editing never changes code, UUID or parent. API schemas forbid extra fields, including
structural fields and client-supplied security/impact assertions. Service signatures expose no
arbitrary changes dictionary. Missing targets return typed 404; validation is 422 and conflicts 409.

Inactive drafts may exist under inactive parents. Activating College requires active Campus;
activating Program requires active Campus and College and known CONFIGURED policy. Parent activation
does not reactivate descendants. Existing unresolved active Programs survive unchanged; a no-op
status call does not retrospectively retire them. Newly activating incomplete policy is blocked;
there is no fabricated approval flag or institutional workflow.

No mutation cascades into StudentAffiliation, CounselorResponsibility, submitted Inventory,
Good Moral, Tracer or historical outputs. Current catalog joins can display a new official name;
saved names/course/certificate facts remain unchanged. Effective-dated names remain deferred.
