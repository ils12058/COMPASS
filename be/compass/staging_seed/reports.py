"""Generated UAT documentation for COMPASS Staging Dataset v1.

Every document is produced from the manifest plus a *passing* read-only verification of the
seeded database, so the catalog cannot drift from the records it describes. Generation refuses to
write if verification failed, and every document is scanned for credential material first.
Nothing here reads or writes a password, MFA secret, token, confidential answer or counseling
narrative; evaluator identities are never included.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from compass.organization.canonical import CANONICAL_CAMPUSES

from . import DATASET_NAME, DATASET_VERSION
from .identities import AccountSpec, AuthPlan, Lifecycle, StudentGroup, StudentSpec, Suitability
from .manifest import (
    ACCOUNTS,
    ACCOUNTS_BY_KEY,
    SCENARIOS,
    UAT_40_ALLOCATION,
    UAT_40_STUDENT_COLLEGES,
    Readiness,
    scenarios_for,
    stakeholder,
)
from .staff import COUNSELOR_RESPONSIBILITIES, STAFF_SUPERVISION
from .students import PROMOTED_BACKGROUND
from .timeline import EARLIEST_ANCHOR, LATEST_ANCHOR

CATALOG = "STAGING-DATASET-v1-ACCOUNT-CATALOG.md"
ACCOUNTS_CSV = "staging-accounts.csv"
GUIDE = "UAT-ACCOUNT-SELECTION-GUIDE.md"
MATRIX = "UAT-SCENARIO-MATRIX.md"
ASSIGNMENT = "UAT-ACCOUNT-ASSIGNMENT-TEMPLATE.csv"
UAT_40_ASSIGNMENTS = "COMPASS-UAT-40-ASSIGNMENTS.csv"
SUMMARY = "STAGING-DATASET-v1-SUMMARY.md"

CSV_COLUMNS = (
    "account_key",
    "institutional_id",
    "full_name",
    "email",
    "role",
    "designation",
    "stakeholder",
    "student_group",
    "student_lifecycle",
    "campus",
    "college",
    "program",
    "year_level",
    "authentication_state",
    "assignment_suitability",
    "scenario_ids",
    "scenario_summary",
    "relevant_preloaded_state",
    "important_limitations",
)
ASSIGNMENT_COLUMNS = (
    "uat_participant_reference",
    "stakeholder_category",
    "selected_account_key",
    "selected_institutional_id",
    "scenario_set",
    "assignment_status",
    "credential_handoff_status",
    "testing_status",
    "notes",
)
# The exact 40-person allocation. Prefilled from the manifest and the verified database; the
# research team fills the blank columns privately and never commits a completed copy.
UAT_40_COLUMNS = (
    "participant_reference",
    "stakeholder_category",
    "college_academic_unit",
    "account_key",
    "institutional_id",
    "login_email",
    "canonical_role",
    "assigned_scenario_ids",
    "participant_full_name",
    "account_distributed_by",
    "credential_handoff_date",
    "participant_acknowledgement",
    "first_login_verified",
    "mfa_enrollment_status",
    "testing_status",
    "remarks",
)
COLLEGE_NAMES = {
    college.code: college.name for campus in CANONICAL_CAMPUSES for college in campus.colleges
}
# Short display labels; Entienza is the Entienza Campus academic unit.
COLLEGE_LABELS = {"ENTIENZA": "Entienza"}
SUITABILITY_LABELS = {
    Suitability.PARTICIPANT: "UAT-ready (assignable)",
    Suitability.BACKGROUND: "Background only",
    Suitability.RESTRICTED: "Restricted (negative tests only)",
}
STAKEHOLDER_ORDER = (
    "Student",
    "Guidance Counselor",
    "Guidance Services Staff",
    "Head Guidance Counselor",
    "IT Administrator",
    "Data Protection Officer",
    "Institutional Officer",
)
# Patterns that would indicate credential or key material leaked into a document.
SECRET_PATTERNS = (
    re.compile(r"gAAAAA[A-Za-z0-9_\-]{20,}"),
    re.compile(r"(pbkdf2_sha256|argon2|bcrypt)\$"),
    re.compile(r"otpauth://", re.IGNORECASE),
    re.compile(r"temporary_password", re.IGNORECASE),
)


class ReportError(RuntimeError):
    """Documentation was not written; the message names the reason, never a value."""


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _table(headers, rows) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows)
    return lines


def _row(account: AccountSpec, result) -> dict[str, str]:
    facts = result.accounts[account.key]
    scenarios = scenarios_for(account.key)
    student = account if isinstance(account, StudentSpec) else None
    return {
        "account_key": account.key,
        "institutional_id": account.institutional_id,
        "full_name": account.full_name,
        "email": facts.email,
        "role": facts.role,
        "designation": ", ".join(facts.designations),
        "stakeholder": stakeholder(account),
        "student_group": student.group.value if student else "",
        "student_lifecycle": facts.lifecycle,
        "campus": facts.campus,
        "college": facts.college,
        "program": facts.program,
        "year_level": facts.year_level,
        "authentication_state": facts.auth_state,
        "assignment_suitability": SUITABILITY_LABELS[account.suitability],
        "scenario_ids": " ".join(scenario.id for scenario in scenarios),
        "scenario_summary": account.summary,
        "relevant_preloaded_state": "; ".join(facts.preloaded),
        "important_limitations": account.limitations,
    }


def _header(title: str, result) -> list[str]:
    return [
        f"# {title}",
        "",
        f"{DATASET_NAME} (dataset version {DATASET_VERSION}). Generated "
        f"{result.generated_at} by `seed_staging_dataset report` from the manifest and a passing "
        f"read-only verification of the {result.app_env} database. Do not edit by hand: change "
        "`be/compass/staging_seed/` and regenerate.",
        "",
        "All names, identifiers, addresses and email addresses are synthetic. This document "
        "contains no passwords, MFA secrets, tokens, confidential form answers or counseling "
        "content, and no evaluator identities.",
        "",
    ]


def _catalog(result) -> str:
    lines = _header("Staging Dataset v1 — Account Catalog", result)
    lines += [
        "Every seeded account is listed. *Authentication state* is read from the database: "
        "accounts are seeded without a password and become sign-in ready only after the "
        "operator runs `seed_staging_dataset issue-credentials`.",
        "",
        "Email addresses use the configured `STAGING_SEED_EMAIL_DOMAIN`; on another staging "
        "deployment only the domain changes.",
        "",
    ]
    staff_headers = (
        "Key",
        "ID",
        "Name",
        "Email",
        "Role",
        "Designation",
        "Auth state",
        "Suitability",
        "Scenarios",
        "Summary",
        "Limitations",
    )
    student_headers = (
        "Key",
        "ID",
        "Name",
        "Email",
        "Lifecycle",
        "Campus/College",
        "Program",
        "Year",
        "Auth state",
        "Suitability",
        "Scenarios",
        "Preloaded state",
        "Limitations",
    )
    for title, accounts in (
        (
            "Staff — UAT-ready",
            [a for a in ACCOUNTS if not a.is_student and a.suitability == Suitability.PARTICIPANT],
        ),
        (
            "Staff — restricted (negative tests)",
            [a for a in ACCOUNTS if not a.is_student and a.suitability == Suitability.RESTRICTED],
        ),
    ):
        lines += [f"## {title}", ""]
        rows = []
        for account in sorted(accounts, key=lambda a: (stakeholder(a), a.key)):
            row = _row(account, result)
            rows.append(
                (
                    row["account_key"],
                    row["institutional_id"],
                    row["full_name"],
                    row["email"],
                    row["role"],
                    row["designation"] or "—",
                    row["authentication_state"],
                    row["assignment_suitability"],
                    row["scenario_ids"] or "—",
                    row["scenario_summary"],
                    row["important_limitations"] or "—",
                )
            )
        lines += [*_table(staff_headers, rows), ""]
    for title, predicate in (
        ("Students — rich scenario (UAT-ready)", lambda s: s.group == StudentGroup.RICH),
        ("Students — action-ready (UAT-ready)", lambda s: s.group == StudentGroup.ACTION_READY),
        (
            "Students — background population promoted to UAT-ready",
            lambda s: (
                s.group == StudentGroup.BACKGROUND and s.suitability == Suitability.PARTICIPANT
            ),
        ),
        (
            "Students — background population",
            lambda s: (
                s.group == StudentGroup.BACKGROUND and s.suitability == Suitability.BACKGROUND
            ),
        ),
        ("Students — restricted", lambda s: s.suitability == Suitability.RESTRICTED),
    ):
        accounts = [a for a in ACCOUNTS if isinstance(a, StudentSpec) and predicate(a)]
        lines += [f"## {title}", ""]
        rows = []
        for account in accounts:
            row = _row(account, result)
            rows.append(
                (
                    row["account_key"],
                    row["institutional_id"],
                    row["full_name"],
                    row["email"],
                    row["student_lifecycle"],
                    f"{row['campus']}/{row['college']}",
                    row["program"],
                    row["year_level"] or "—",
                    row["authentication_state"],
                    row["assignment_suitability"],
                    row["scenario_ids"] or "—",
                    row["relevant_preloaded_state"] or "—",
                    row["important_limitations"] or "—",
                )
            )
        lines += [*_table(student_headers, rows), ""]
    return "\n".join(lines)


def _accounts_csv(result) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for account in ACCOUNTS:
        writer.writerow(_row(account, result))
    return buffer.getvalue()


GUIDE_NOTES = {
    "Student": (
        "Give each Student evaluator their own action-ready or rich account. Action-ready "
        "accounts (`ar_…`) each start from one pending action, so two evaluators never need the "
        "same Student. Rich accounts carry multi-domain history for exploratory testing. Seven "
        "background Students are promoted to UAT-ready so every College is represented; they "
        "start from their seeded records."
    ),
    "Guidance Counselor": (
        "Three Counselors own separate caseloads (Main CCMS/CAS/COENG, Main CBPA + Abaño COED, "
        "satellite campuses). Assign one evaluator per Counselor account; their Work Queues and "
        "rosters do not overlap except for office-wide Good Moral work."
    ),
    "Guidance Services Staff": (
        "Each staff account is supervised by one Counselor and works within that caseload. "
        "Assign gss_a with counselor_a's evaluator team and gss_b with counselor_b's."
    ),
    "Head Guidance Counselor": (
        "One Head account exists, as at the institution. If two evaluators share it, schedule "
        "their mutating scenarios (opportunities, reopen, reassignment) one at a time."
    ),
    "IT Administrator": (
        "Three equivalent accounts let three ITSO evaluators work independently. Use newly created "
        "synthetic accounts for account-management changes; never edit dataset accounts."
    ),
    "Data Protection Officer": (
        "Two DPO accounts share one Privacy Notice catalog. Publishing a revision prompts every "
        "signed-in user, so schedule DPO-NOT-01 with the UAT lead."
    ),
    "Institutional Officer": (
        "The undesignated officer exists only to prove refusals; issue its credential explicitly."
    ),
}


def _guide(result) -> str:
    lines = _header("UAT Account Selection Guide", result)
    lines += [
        "How to choose seeded accounts for stakeholder UAT. Recommendations follow the "
        "scenario matrix; the account catalog lists every account.",
        "",
        "## Rules for every assignment",
        "",
        "- Assign each UAT-ready account to **one** evaluator. Mutating scenarios change the "
        "account's state, and a rerun of the seeder never restores a consumed state.",
        "- Never assign background accounts as delivered; they populate rosters and reports. To "
        "use one, add it to the manifest as a participant and regenerate.",
        "- Restricted accounts are for negative-authorization tests only. Disabled accounts "
        "cannot receive credentials; the others need `issue-credentials --account <key>`.",
        f"- Record assignments only in a private copy of `{UAT_40_ASSIGNMENTS}` (or "
        f"`{ASSIGNMENT}` for reserves); never commit evaluator names or contact details.",
        "- Credentials are delivered privately from the protected handoff file; this guide and "
        "the catalog never contain them.",
        "",
        "## 40-person UAT allocation",
        "",
        "Each key below belongs to a different participant. Alumni use the STUDENT role with "
        "GRADUATED lifecycle; ITSO personnel use IT_ADMIN. This allocation is not authorization "
        "to issue credentials. Every current Student is CURRENT and affiliated with the College "
        "shown; no onboarding, restricted, disabled, former or graduated account fills a "
        "current-Student slot. Promoted background Students complete the College distribution: "
        + ", ".join(f"`{key}`" for key in PROMOTED_BACKGROUND)
        + ".",
        "",
        *_table(
            ("Participant category", "Count", "Exact account keys"),
            [
                (category, len(keys), ", ".join(f"`{key}`" for key in keys))
                for category, keys in UAT_40_ALLOCATION.items()
            ],
        ),
        "",
        "### Current Students by College / academic unit",
        "",
        *_table(
            ("College / academic unit", "Name", "Students", "Account keys"),
            [
                (
                    _college_label(college),
                    COLLEGE_NAMES[college],
                    len(keys),
                    ", ".join(f"`{key}`" for key in keys),
                )
                for college, keys in UAT_40_STUDENT_COLLEGES.items()
            ],
        ),
        "",
        "Keep one evaluator per account. Confirm mailbox ownership and staff authenticator "
        f"enrollment before issuance; record actual assignments only in a private copy of "
        f"`{UAT_40_ASSIGNMENTS}`, which lists exactly these 40 accounts. Reserve UAT-ready "
        "accounts outside the allocation: " + ", ".join(f"`{key}`" for key in _reserves()) + ".",
        "",
        "Issue credentials for exactly these 40 keys, never with an unrestricted command:",
        "",
        "```",
        "seed_staging_dataset issue-credentials --output <new protected handoff file> \\",
        *(
            f"  --account {key}" + (" \\" if number < 40 else "")
            for number, key in enumerate(_allocated(), 1)
        ),
        "```",
        "",
    ]
    for role in STAKEHOLDER_ORDER:
        accounts = [a for a in ACCOUNTS if stakeholder(a) == role]
        if not accounts:
            continue
        lines += [f"## {role}", "", GUIDE_NOTES[role], ""]
        rows = []
        allocated = set(_allocated())
        for account in accounts:
            if account.suitability == Suitability.BACKGROUND:
                continue
            scenarios = scenarios_for(account.key)
            mutating = any(s.mutating for s in scenarios)
            rows.append(
                (
                    account.key,
                    account.institutional_id,
                    account.label,
                    SUITABILITY_LABELS[account.suitability],
                    "Allocated"
                    if account.key in allocated
                    else ("Reserve" if account.suitability == Suitability.PARTICIPANT else "—"),
                    " ".join(s.id for s in scenarios) or "—",
                    "Yes — state changes" if mutating else "No — read-only",
                    account.summary,
                    account.limitations or "—",
                )
            )
        lines += _table(
            (
                "Account",
                "ID",
                "Why recommended",
                "Assignable",
                "40-person UAT",
                "Scenarios",
                "Initial state changes?",
                "What it starts with",
                "Conflicts / limitations",
            ),
            rows,
        )
        background = [a.key for a in accounts if a.suitability == Suitability.BACKGROUND]
        if background:
            lines += [
                "",
                f"Background-only ({len(background)}): "
                + ", ".join(f"`{key}`" for key in background)
                + ". They appear in rosters, filters and reports and are the targets named "
                "by some staff scenarios; do not assign them to evaluators.",
            ]
        lines.append("")
    lines += [
        "## Known shared-state conflicts",
        "",
        "- `ar_24`: STU-GM-02 (request Good Moral) and HGC-EXIT-01 (reopen the Exit Interview) "
        "start from the same submitted interview; run the Head scenario last.",
        "- `ar_05`: CNS-EC-01 (Counselor requests consent) must precede STU-EC-01 (Student "
        "decides); assign both to the same scheduled pair of evaluators.",
        "- `bg_54`: CNS-GM-04 (counselor_c starts an assisted Good Moral request) must precede "
        "STU-GM-08; the Student must not request a certificate first, because an open request "
        "blocks the assisted one.",
        "- `head_guidance`, `dpo`/`dpo_2`: shared catalogs; serialize mutating scenarios.",
        "- Changing Counselor responsibilities, Availability or the current Academic Year affects "
        "most scenarios; keep those out of UAT or run them last.",
        "",
    ]
    return "\n".join(lines)


def _matrix(result) -> str:
    lines = _header("UAT Scenario Matrix", result)
    executable = [s for s in SCENARIOS if s.readiness == Readiness.EXECUTABLE]
    pending = [s for s in SCENARIOS if s.readiness != Readiness.EXECUTABLE]
    lines += [
        f"{len(executable)} executable scenarios and {len(pending)} pending-implementation "
        "scenarios. *Readiness* is READY when verification proved every documented initial "
        "state, CHANGED when an evaluator has already changed it (active UAT), and "
        "PENDING_IMPLEMENTATION when the feature is not merged.",
        "",
    ]
    domains: dict[str, list] = {}
    for scenario in SCENARIOS:
        domains.setdefault(
            scenario.role
            if scenario.readiness == Readiness.EXECUTABLE
            else "Pending pre-defense features",
            [],
        ).append(scenario)
    for title in (*STAKEHOLDER_ORDER, "Pending pre-defense features"):
        scenarios = domains.get(title)
        if not scenarios:
            continue
        lines += [f"## {title}", ""]
        lines += _table(
            (
                "ID",
                "Feature",
                "Scenario",
                "Account",
                "Start route",
                "Initial state",
                "Test action",
                "Expected result",
                "Mutating / fresh state",
                "Restrictions",
                "Readiness",
            ),
            [
                (
                    s.id,
                    s.domain,
                    s.title,
                    s.account,
                    f"`{s.route}`",
                    s.initial_state,
                    s.action,
                    s.expected,
                    f"{'Mutating' if s.mutating else 'Read-only'} / "
                    f"{'needs fresh state to repeat' if s.fresh_state else 'repeatable'}",
                    " ".join(filter(None, (s.preconditions, s.restrictions))),
                    result.scenario_status[s.id],
                )
                for s in scenarios
            ],
        )
        lines.append("")
    return "\n".join(lines)


def _assignment_template() -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(ASSIGNMENT_COLUMNS)
    for account in ACCOUNTS:
        if account.suitability != Suitability.PARTICIPANT:
            continue
        writer.writerow(
            (
                "",
                stakeholder(account),
                account.key,
                account.institutional_id,
                " ".join(s.id for s in scenarios_for(account.key)),
                "UNASSIGNED",
                "NOT_ISSUED",
                "NOT_STARTED",
                "",
            )
        )
    return buffer.getvalue()


def _college_label(code: str) -> str:
    return COLLEGE_LABELS.get(code, code)


def _allocated() -> list[str]:
    return [key for keys in UAT_40_ALLOCATION.values() for key in keys]


def _reserves() -> list[str]:
    allocated = set(_allocated())
    return [
        a.key
        for a in ACCOUNTS
        if a.suitability == Suitability.PARTICIPANT
        and a.auth == AuthPlan.CREDENTIAL
        and a.key not in allocated
    ]


def _caseload(counselor_key: str) -> str:
    colleges = [
        _college_label(college)
        for counselor, _campus, college in COUNSELOR_RESPONSIBILITIES
        if counselor == counselor_key
    ]
    return f"{', '.join(colleges)} caseload"


def _uat_40_unit(account: AccountSpec) -> str:
    if isinstance(account, StudentSpec):
        label = _college_label(account.college_code)
        return label if account.lifecycle == Lifecycle.CURRENT else f"{label} (graduated)"
    if "HEAD_GUIDANCE_COUNSELOR" in account.designations:
        return "Guidance and Counseling Office (institution-wide)"
    if account.role == "COUNSELOR":
        return f"Guidance and Counseling Office ({_caseload(account.key)})"
    if account.role == "GUIDANCE_SERVICES_STAFF":
        supervisor = dict(STAFF_SUPERVISION)[account.key]
        return f"Guidance and Counseling Office ({_caseload(supervisor)})"
    if account.role == "IT_ADMIN":
        return "ITSO"
    return "Data Protection Office"


def uat_40_rows(result) -> list[dict[str, str]]:
    """The 40 assignment rows in allocation order; evaluator columns stay blank."""

    rows = []
    entries = [(category, key) for category, keys in UAT_40_ALLOCATION.items() for key in keys]
    for number, (category, key) in enumerate(entries, 1):
        account = ACCOUNTS_BY_KEY[key]
        facts = result.accounts[key]
        prefilled = {
            "participant_reference": f"UAT40-{number:02d}",
            "stakeholder_category": category,
            "college_academic_unit": _uat_40_unit(account),
            "account_key": key,
            "institutional_id": account.institutional_id,
            "login_email": facts.email,
            "canonical_role": facts.role,
            "assigned_scenario_ids": " ".join(
                s.id for s in scenarios_for(key) if s.readiness == Readiness.EXECUTABLE
            ),
        }
        rows.append({column: prefilled.get(column, "") for column in UAT_40_COLUMNS})
    return rows


def _uat_40_csv(result) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=UAT_40_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(uat_40_rows(result))
    return buffer.getvalue()


def _dict_table(title: str, values: dict) -> list[str]:
    return [f"### {title}", "", *_table(("Value", "Count"), list(values.items())), ""]


def _summary(result) -> str:
    counts = result.counts
    lines = _header("Staging Dataset v1 — Summary", result)
    sections = "; ".join(
        f"{s.name}: {s.passed_count} passed, {len(s.failures)} failed, {len(s.warnings)} warnings"
        for s in result.sections
    )
    lines += [
        "## Dataset",
        "",
        f"- Dataset: **{DATASET_NAME}**, dataset version **{DATASET_VERSION}** (independent of "
        "the COMPASS application and API versions; not an upgrade of Demo Dataset v1/v2).",
        "- Timeline: Academic Years 2024-2025, 2025-2026 and current 2026-2027, Asia/Manila. "
        f"Preparation dates supported: {EARLIEST_ANCHOR.isoformat()} to "
        f"{LATEST_ANCHOR.isoformat()}. Seed runs recorded on: "
        f"{', '.join(result.preparation_dates) or 'none'}.",
        f"- Accounts: **{counts['accounts']}** ({counts['students']} Students, "
        f"{counts['staff']} staff).",
        "- UAT allocation: **40 independent participants** — 1 Head, 3 Counselors, "
        "2 Guidance Services Staff, 25 current Students, 5 graduated Alumni, 3 ITSO and 1 DPO. "
        "Current Students by College: "
        + ", ".join(
            f"{_college_label(college)} {len(keys)}"
            for college, keys in UAT_40_STUDENT_COLLEGES.items()
        )
        + f". See the Selection Guide and `{UAT_40_ASSIGNMENTS}` for exact account keys; "
        "credential issuance remains separate.",
        f"- Executable UAT scenarios: **{counts['scenarios_executable']}**; "
        f"pending-implementation scenarios: **{counts['scenarios_pending']}**.",
        f"- Verification: **{'PASSED' if result.passed else 'FAILED'}** — {sections}.",
        "",
        "## Accounts",
        "",
        *_dict_table("Students by group", counts["by_group"]),
        *_dict_table("Accounts by assignment suitability", counts["by_suitability"]),
        *_dict_table("UAT-ready accounts by role", counts["participants_by_role"]),
        *_dict_table("Authentication state (from the database)", counts["by_auth_state"]),
        *_dict_table("Students by lifecycle", counts["by_lifecycle"]),
        "## Academic distribution",
        "",
        *_dict_table("Students by enrollment campus", counts["by_campus"]),
        *_dict_table("Students by College", counts["by_college"]),
        *_dict_table("Students by Program", counts["by_program"]),
        *_dict_table("Current Students by year level", counts["by_year_level"]),
        "## Workflow states",
        "",
        *_dict_table("Current-year Individual Inventory", counts["current_inventory"]),
        *_dict_table("Appointments", counts["appointments"]),
        *_dict_table("Appointment delivery modes", counts["appointment_modes"]),
        *_dict_table("Student Session Summaries", counts["student_session_summaries"]),
        *_dict_table("Routine Interviews", counts["routine_interviews"]),
        *_dict_table("Referrals", counts["referrals"]),
        *_dict_table("Call Slips", counts["call_slips"]),
        *_dict_table("Good Moral requests", counts["good_moral"]),
        *_dict_table("Exit Interviews", counts["exit_interviews"]),
        *_dict_table("Graduate Tracer", counts["graduate_tracer"]),
        *_dict_table("Student notifications", counts["notifications"]),
        *_dict_table("Announcements", counts["announcements"]),
        *_dict_table("Resources", counts["resources"]),
        "### Other totals",
        "",
        *_table(
            ("Record", "Count"),
            [
                ("Inventories (all years)", counts["inventories_total"]),
                ("Counseling Encounters", counts["encounters"]),
                ("Referral actions", counts["referral_actions"]),
                ("Open Exit Interview opportunities", counts["exit_opportunities_open"]),
                ("Guidance Message threads", counts["guidance_threads"]),
                ("Customer Feedback responses", counts["customer_feedback"]),
                ("CSM responses", counts["csm_responses"]),
                (
                    "Colleges with a Counselor",
                    f"{counts['colleges_covered']} of {counts['colleges_total']}",
                ),
            ],
        ),
        "",
        "## Known limitations",
        "",
        "- The population is a UAT design, not a statistical model of UCN enrollment.",
        "- The Graduate School has no Counselor responsibility and no seeded Students.",
        "- No Daily room, recording, transcript or provider session is created; joining an "
        "E-Counseling call needs an operator-approved provider plan.",
        "- Structured PSGC geography stays 'not specified'; no Resource files are uploaded.",
        "- Seeding creates in-app notifications only; live UAT actions send normal staging email "
        "to the dataset addresses.",
        "- Appointment Reminders, Service Catalog Expansion and Shared Guidance Follow-Up "
        "Management are pending; their scenarios are not executable on this baseline.",
        "",
    ]
    return "\n".join(lines)


def _scan(name: str, text: str) -> None:
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise ReportError(f"{name} contains credential-like material; nothing was written.")


def render_reports(result) -> dict[str, str]:
    documents = {
        CATALOG: _catalog(result),
        ACCOUNTS_CSV: _accounts_csv(result),
        GUIDE: _guide(result),
        MATRIX: _matrix(result),
        ASSIGNMENT: _assignment_template(),
        UAT_40_ASSIGNMENTS: _uat_40_csv(result),
        SUMMARY: _summary(result),
    }
    for name, text in documents.items():
        _scan(name, text)
    return documents


def write_reports(result, output_dir: Path) -> list[Path]:
    if not result.passed:
        raise ReportError("Verification failed; documentation was not written.")
    documents = render_reports(result)
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, text in documents.items():
        path = output_dir / name
        path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        written.append(path)
    return written


__all__ = [
    "ACCOUNTS_CSV",
    "ASSIGNMENT",
    "ASSIGNMENT_COLUMNS",
    "CATALOG",
    "CSV_COLUMNS",
    "GUIDE",
    "MATRIX",
    "ReportError",
    "SUMMARY",
    "UAT_40_ASSIGNMENTS",
    "UAT_40_COLUMNS",
    "render_reports",
    "uat_40_rows",
    "write_reports",
]
