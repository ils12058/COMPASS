# FUP-1C + FUP-2A implementation record

**Authority:** every behavior and string below is **Provisional — pending GCO**. This is an
engineering record, not institutional approval.

## 1. Backend projection

### 1.1 Schema

`FollowUpSummary` in `be/compass/guidance_followups/api.py` now carries:

```text
source_unavailable: bool
```

`FollowUpDetail` inherits the field from `FollowUpSummary`; it no longer declares its own copy. The
summary never carries `source`, `source_id`, `source_kind`, a source title, a source reference or any
other source-derived identity. The only source-related fact the list receives is this boolean.

`FollowUpSummary` is used by:

- `guidanceFollowupsList` (`GET /api/v1/guidance-followups`);
- `guidanceFollowupsRecoverable` (`GET /api/v1/guidance-followups/recoverable`).

`FollowUpDetail` is used by detail, create, update, reassign, activity, complete, cancel and history
responses.

### 1.2 Value semantics

`source_unavailable` is `true` only when all of the following hold:

1. the task has both `source_kind` and `source_id`;
2. the current actor cannot read that source under the **same check used by detail**.

The check is `policy.source_is_visible`, a new shared helper:

```python
def source_is_visible(actor, *, kind, source_id, student_id):
    if not kind or not source_id:
        return False
    try:
        require_source(actor, kind=kind, source_id=source_id, student_id=student_id)
    except FollowUpNotFound:
        return False
    return True
```

`visible_source` — which produces the detail `source` reference — now calls the same helper. Therefore
list and detail use one visibility rule, including the type-specific source checks for Counseling
Encounter, Routine Interview and Referral, and the same `manage=False` capability boundary.

Source-free tasks are always `false`. The field is `false` for a readable source regardless of source
kind.

### 1.3 Batching for the returned page

`_summaries(actor, items)` computes visibility once per distinct `(source_kind, source_id)` pair on the
returned page:

```python
visibility = {}
for item in items:
    if no source:
        source_unavailable = False
    else:
        key = (item.source_kind, item.source_id)
        if key not in visibility:
            visibility[key] = policy.source_is_visible(...)
        source_unavailable = not visibility[key]
```

Consequences:

- one visibility check per distinct source on the page, not per task;
- duplicate sources on a page cost one check;
- no full-table scan and no unbounded loop beyond the returned page;
- authorization, pagination, ordering and mutations are unchanged.

`_summaries` is called by the list and recoverable endpoints. Detail does not run a second check: it
derives the boolean from `followup_detail`'s `source` value, which itself came from `visible_source`.
The minimized creation receipt now computes the actual visibility through `policy.source_is_visible`
instead of the previous blanket `bool(item.source_id)`; this is a projection consistency fix, not an
authorization change.

### 1.4 Report

No report counter, aggregate or per-task field was added. `FollowUpReport` remains aggregate-only.
The report screen adds explanatory copy under Workload only.

## 2. Contract regeneration

Run from the repository root, in this order:

```bash
DJANGO_SETTINGS_MODULE=tests.settings PYTHONPATH=be be/.venv/bin/python be/manage.py export_openapi
DJANGO_SETTINGS_MODULE=tests.settings PYTHONPATH=be be/.venv/bin/python be/manage.py export_openapi --check
pnpm --dir fe api:generate
```

Result:

- the export wrote `contracts/openapi.json`;
- the check reported the contract current;
- Orval regenerated `fe/src/lib/api/generated/**`.

Tracked contract diff (`git diff --stat -- contracts/openapi.json fe/src/lib/api/generated`):

```text
 contracts/openapi.json | 7 ++++++-
 1 file changed, 6 insertions(+), 1 deletion(-)
```

The diff contains only:

- `source_unavailable` added to `FollowUpSummary.properties` and `FollowUpSummary.required`;
- `source_unavailable` moved into the inherited position in `FollowUpDetail.required` (the property
  remains present in both schemas).

`fe/src/lib/api/generated/` is gitignored (`.gitignore:23`), so it produces no tracked diff even after
regeneration. Both generated models were verified on disk:

```text
fe/src/lib/api/generated/model/followUpSummary.ts:22:  source_unavailable: boolean;
fe/src/lib/api/generated/model/followUpDetail.ts:33:  source_unavailable: boolean;
```

No unrelated contract or generated drift was observed. No generated file was hand-edited.

## 3. Frontend changes

### 3.1 List indicator

In `followups-list.tsx`, inside the existing Status cell:

```tsx
{statusLabel(row.status)}
{row.source_unavailable
  ? <span className="block text-sm text-muted">Related record unavailable</span>
  : null}
```

- muted text, no danger color, no icon, no source title and no source link;
- the row remains fully actionable and the Student link is unchanged;
- there is no new button, filter or column;
- the text is real text, so a screen reader reads it without relying on color.

Exact string: `Related record unavailable`

### 3.2 Report note

In `followups-report.tsx`, under Workload after the period line:

> Source availability is shown on each follow-up. This report counts only follow-ups you can access
> and does not include related-record details.

### 3.3 Completion copy

In the `Completion outcome` section of `followups-detail.tsx`, after the "Completed by …" line:

> Completing this follow-up ends this task. It does not close the related record. If more work is
> needed, create a new follow-up.

Copy only. No "Create next follow-up" button, link, checkbox or action was added, and the existing
completion and cancellation confirmation dialogs are unchanged.

### 3.4 Help

In `followups-help.tsx`, after "Progress":

**Heading:** `Completion and further action`

**Content:**

> Completing a follow-up ends that task. It does not close the related record. If more work is needed,
> create a new follow-up.

## 4. Tests

### 4.1 Backend — `be/tests/test_guidance_followups.py`

| Test | Assertion |
|---|---|
| `test_list_projects_source_unavailable_for_voided_referral` | Before voiding, the list row is `false`; after voiding, the operational Pending task is still returned with `true`; the row has no source identity keys |
| `test_list_source_unavailable_false_for_readable_and_source_free` | A readable Referral task and a standalone task both return `false` |
| `test_list_and_detail_agree_on_source_unavailable` | For the same actor and voided-source task, list and detail return the same `true`, and detail still returns `source: null` |
| `test_source_unavailable_projection_does_not_leak_source_identity` | The list row has no source identity keys, and the response body contains no source UUID, reference code, reason or referrer name |

The existing confidential-source-loss test was not duplicated or changed.

### 4.2 Browser — `fe/tests/guidance-followups.browser.mjs`

The synthetic world gained a `listAvailability: "mixed"` fixture with three rows:

- an unavailable-source row (`source_unavailable: true`, `source: null`);
- a readable-source row (`source_unavailable: false`, with a source reference);
- a standalone row (`source_unavailable: false`, `source: null`).

New and extended checks:

- `Follow-Up list marks only an unavailable related record without exposing source identity` — exactly
  one indicator, absent on readable and standalone rows, no source link, no source ID, no source kind,
  Student link still present;
- `Follow-Up report explains source availability without a per-task projection` — Workload copy is
  visible and no indicator leaks into the report;
- completed-task check now asserts the completion paragraph;
- Help check now asserts the `Completion and further action` heading and content.

`fe/tests/guidance-followups.test.mjs` was not changed because no pure helper was introduced.

## 5. Explicit exclusions

No change was made to `models.py`, `services.py` authorization, migrations, notifications, seeds,
package files, OpenAPI operations, generated code by hand, `followups-context.tsx`,
`followups-shared.tsx`, or any unrelated frontend file. FUP-1D, FUP-2B, FUP-2C and FUP-3 were not
implemented. No report counter or per-task report field exists.
