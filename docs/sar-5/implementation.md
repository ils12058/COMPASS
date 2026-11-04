# SAR-5 implementation — legacy residue retirement

## 1. Pre-change proof for the reason code

Before changing the identifier:

```bash
rg -n "NO_AFFILIATION" be/compass fe/src be/tests
```

result:

```text
be/compass/organization/services.py:99:        return DefaultCounselorResolution(None, "UNRESOLVED", "NO_AFFILIATION")
```

```bash
rg -n "resolution\.reason|\.reason ==" be/compass
```

returned only unrelated fields (`account_management` rejection reason, Notification email
presentation reasons). No caller branches on `DefaultCounselorResolution.reason`:

- `be/compass/appointments/services.py` reads only `resolution.counselor`;
- `be/compass/guidance_messages/services.py` reads only `resolution.counselor`;
- no test asserted `NO_AFFILIATION`.

## 2. A1 — counselor-resolution reason code

File: `be/compass/organization/services.py`

Before:

```python
return DefaultCounselorResolution(None, "UNRESOLVED", "NO_AFFILIATION")
```

After:

```python
return DefaultCounselorResolution(None, "UNRESOLVED", "NO_PLACEMENT")
```

Condition and behavior are unchanged: an active Student with no current academic placement
resolves to no default counselor. The other reason codes (`INVALID_STUDENT`,
`INACTIVE_ORGANIZATION`, `NO_HEAD_FALLBACK`, `AMBIGUOUS_HEAD_CONFIGURATION`) still describe their
conditions accurately and were not renamed.

New test in `be/tests/test_organization.py`:

```python
@pytest.mark.django_db
def test_default_counselor_reports_missing_academic_placement():
    sync_policy()
    student = make_user("no-placement@example.edu", "STUDENT")

    result = resolve_default_counselor_for_student(student)
    assert result.counselor is None
    assert result.source == "UNRESOLVED"
    assert result.reason == "NO_PLACEMENT"

    StudentAcademicProfile.objects.create(student=student)
    result = resolve_default_counselor_for_student(student)
    assert result.counselor is None
    assert result.reason == "NO_PLACEMENT"
```

It covers the absent-profile path and the present-but-unplaced profile path.

## 3. A2 — PDF coverage label

File: `be/compass/reports/pdf.py`, function `_filter_rows`

Before:

```python
by_affiliation = "Applied — Student's current Guidance affiliation"
```

After:

```python
by_placement = "Applied — Student's current academic placement"
```

The variable is renamed at all three uses: the Reporting scope row, the Campus/College filter
coverage effect, and the per-filter coverage effect loop. This is the label that states what the
Campus/College filters actually use; the data source was already
`student_academic_profile__current_college` in `reports/services.py`, so only the wording moved.

Updated assertion in `be/tests/test_student_profiling_pdf.py`
(`test_filter_table_and_metadata_distinguish_selected_filters_from_reporting_scope`):

Before: `"Applied — Student's current Guidance affiliation"`

After: `"Applied — Student's current academic placement"`

## 4. A3 — methodology coverage note

File: `be/compass/reports/services.py`, `CURRENT_COVERAGE_NOTE`

Before:

```text
College coverage filters, when supplied, use each Student's current Guidance College
affiliation rather than the Program recorded on the Inventory, so coverage and the profile
population can count different Students.
```

After:

```text
College coverage filters, when supplied, use each Student's current academic College
placement rather than the Program recorded on the Inventory, so coverage and the profile
population can count different Students.
```

Strengthened `test_methodology_is_explicit_and_no_report_persistence_models_exist` in
`be/tests/test_student_profiling_report_coverage.py`:

```python
assert "academic College placement" in report["methodology"]["coverage_note"]
assert "Guidance" not in report["methodology"]["coverage_note"]
```

## 5. Report-wording boundary

Only two rendered Student-affiliation strings changed. The following were deliberately not
touched:

- coverage denominators, inclusion rules and the profile population;
- `applied_filters` / `ignored_filters` membership and every applied/ignored label except the one
  Student-placement label;
- reconciliation counts;
- `HISTORICAL_COVERAGE_NOTE` and `PROFILE_METHODOLOGY`;
- XLSX and PDF table structure, column counts and row order;
- the Campus profile-filter label and all Program/Year Level wording.

No report behavior depends on the changed strings: nothing parses either label, and `applied_filters`
carries canonical keys rather than display text.

## 6. Faculty wording and historical documents

- `FacultyAffiliation`, `faculty_affiliation` API fields, `ManagedFacultyAffiliation` and every
  Faculty use of "affiliation" remain correct and unchanged.
- `docs/org-0/**`, `docs/sar-0/**` through `docs/sar-4/**` and `be/docs/decisions/ADR-*` keep their
  original wording. `NO_AFFILIATION` and the old PDF label remain there as history; no supersession
  notes were added to ADRs.
- `docs/sar-2a/decisions.md` still records the residues as they were at SAR-2A. This file records
  their deliberate retirement.

## 7. Files changed

| File | Change |
|---|---|
| `be/compass/organization/services.py` | `NO_AFFILIATION` → `NO_PLACEMENT` |
| `be/compass/reports/pdf.py` | `by_affiliation` → `by_placement`; label text |
| `be/compass/reports/services.py` | `CURRENT_COVERAGE_NOTE` wording |
| `be/tests/test_organization.py` | new `test_default_counselor_reports_missing_academic_placement` |
| `be/tests/test_student_profiling_pdf.py` | updated filter-label assertion |
| `be/tests/test_student_profiling_report_coverage.py` | strengthened coverage-note assertions |
| `docs/sar-5/**` | this documentation package |

No model, migration, API schema, frontend source or capability file changed.
