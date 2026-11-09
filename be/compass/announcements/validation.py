"""Stable field issue identifiers and safe validation copy."""

ISSUES: dict[str, tuple[str, str]] = {
    "title_text_required": ("title", "Enter a title as text."),
    "title_required": ("title", "Add a title before publishing this Announcement."),
    "title_too_long": ("title", "Keep the title to 200 characters or fewer."),
    "body_text_required": ("body_markdown", "Enter body text."),
    "body_required": ("body_markdown", "Add body text before publishing this Announcement."),
    "body_too_large": ("body_markdown", "Keep the body to 50 KB or less."),
    "page_invalid": ("page", "Choose a page number of 1 or more."),
    "page_size_invalid": ("page_size", "Choose between 1 and 50 results per page."),
    "unsupported_fields": ("", "Review the Announcement details and try again."),
    "ordering_invalid": ("ordering", "Choose a Announcement order."),
    "audience_invalid": ("audience", "Choose an audience."),
    "expiry_invalid": ("expires_at", "Enter a valid expiry date and time."),
    "expiry_not_future": (
        "expires_at",
        "Choose a future expiry time, or archive this Announcement to remove it now.",
    ),
    "status_invalid": ("status", "Choose an Announcement status."),
    "pin_invalid": ("is_pinned", "Choose whether to pin this Announcement."),
    "announcement_archived": ("", "You can't edit an archived Announcement."),
    "publication_requires_draft": ("", "You can publish only a draft Announcement."),
    "announcement_already_archived": ("", "This Announcement is already archived."),
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
