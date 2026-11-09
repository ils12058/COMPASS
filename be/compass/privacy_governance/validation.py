"""Stable field issue identifiers and safe validation copy."""

ISSUES: dict[str, tuple[str, str]] = {
    "page_invalid": ("page", "Choose a page number between 1 and 100,000."),
    "page_size_invalid": ("page_size", "Choose between 1 and 50 results per page."),
    "code_invalid": (
        "code",
        "Use 2–64 letters, digits, dots, underscores or hyphens, starting with a letter or digit.",
    ),
    "record_invalid": ("", "Review the privacy record details and try again."),
    "audiences_required": ("audiences", "Choose at least one audience and no more than three."),
    "audiences_invalid": ("audiences", "Choose Public, Students or Staff as the audience."),
    "audiences_duplicate": ("audiences", "Choose each audience only once."),
    "acknowledgment_invalid": (
        "requires_acknowledgment",
        "Choose whether this notice requires acknowledgment.",
    ),
    "effective_date_invalid": ("effective_on", "Enter a valid effective date."),
    "unsupported_revision_fields": ("", "Review the notice revision details and try again."),
    "code_required": ("code", "Enter a code."),
    "code_too_long": ("code", "Keep the code to 64 characters or fewer."),
    "code_text_required": ("code", "Enter the code as text."),
    "name_required": ("name", "Enter a name."),
    "name_too_long": ("name", "Keep the name to 160 characters or fewer."),
    "name_text_required": ("name", "Enter the name as text."),
    "title_required": ("title", "Enter a title."),
    "title_too_long": ("title", "Keep the title to 200 characters or fewer."),
    "title_text_required": ("title", "Enter the title as text."),
    "summary_required": ("summary", "Enter a summary."),
    "summary_too_long": ("summary", "Keep the summary to 2,000 characters or fewer."),
    "summary_text_required": ("summary", "Enter the summary as text."),
    "body_required": ("body", "Enter body text."),
    "body_too_long": ("body", "Keep the body to 20,000 characters or fewer."),
    "body_text_required": ("body", "Enter the body as text."),
}


def issue_details(identifier: str) -> list[dict[str, object]]:
    field, message = ISSUES[identifier]
    return [{"loc": [field] if field else [], "type": identifier, "message": message}]


# Document the domain vocabulary once on its create operation. All routes use the
# existing ValidationIssue envelope: the identifier is error.details[].type.
VALIDATION_OPENAPI = {
    "x-domain-validation-issues": {
        key: {"loc": [field] if field else []} for key, (field, _) in ISSUES.items()
    }
}
