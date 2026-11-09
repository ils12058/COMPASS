"""Stable field issue identifiers and safe validation copy."""

ISSUES: dict[str, tuple[str, str]] = {
    "title_text_required": ("title", "Enter a title as text."),
    "title_required": ("title", "Add a title before publishing this Resource."),
    "title_too_long": ("title", "Keep the title to 200 characters or fewer."),
    "body_text_required": ("body_markdown", "Enter body text."),
    "body_required": ("body_markdown", "Add body text before publishing this Resource."),
    "body_too_large": ("body_markdown", "Keep the body to 50 KB or less."),
    "external_url_text_required": ("external_url", "Enter a link address or leave it blank."),
    "external_url_required": (
        "external_url",
        "Enter the link address before publishing this Resource.",
    ),
    "external_url_too_long": (
        "external_url",
        "Keep the link address to 2,048 characters or fewer.",
    ),
    "external_url_invalid": ("external_url", "Start the link address with https:// or http://."),
    "external_url_credentials": (
        "external_url",
        "Use a link address without a user name or password.",
    ),
    "display_order_integer_required": (
        "display_order",
        "Enter a whole number for the display order.",
    ),
    "display_order_out_of_range": (
        "display_order",
        "Enter a display order between -2,147,483,648 and 2,147,483,647.",
    ),
    "page_invalid": ("page", "Choose a page number of 1 or more."),
    "page_size_invalid": ("page_size", "Choose between 1 and 50 results per page."),
    "article_attachment_not_allowed": (
        "kind",
        "Articles cannot have a link address or attached file.",
    ),
    "external_link_file_not_allowed": (
        "kind",
        "External link Resources cannot have an attached file.",
    ),
    "file_external_url_not_allowed": ("external_url", "File Resources cannot have a link address."),
    "pdf_required_for_publication": ("file", "Attach a PDF file before publishing this Resource."),
    "external_url_not_allowed": (
        "external_url",
        "Only External link Resources can have a link address.",
    ),
    "unsupported_fields": ("", "Review the Resource details and try again."),
    "pdf_required": ("file", "Choose a PDF file to attach."),
    "pdf_content_type_invalid": ("file", "Choose a PDF file."),
    "pdf_empty": ("file", "Choose a file that is not empty."),
    "pdf_too_large": ("file", "Choose a PDF file of 10 MB or less."),
    "pdf_signature_invalid": ("file", "Choose a valid PDF file."),
    "resource_archived": ("", "You can't edit an archived Resource."),
    "published_kind_immutable": ("kind", "You can't change the type of a published Resource."),
    "attached_file_kind_immutable": (
        "kind",
        "Remove or replace this draft Resource to use a different type.",
    ),
    "file_attachment_requires_draft": (
        "file",
        "You can attach or replace a file only while the Resource is a draft.",
    ),
    "file_attachment_requires_file_kind": (
        "kind",
        "Choose the File Resource type before attaching a file.",
    ),
    "file_attachment_changed": (
        "file",
        "This Resource changed. Review its type and status before attaching a file.",
    ),
    "management_file_missing": ("file", "This Resource has no attached file."),
    "file_removal_requires_draft_file": (
        "file",
        "You can remove a file only from a draft File Resource.",
    ),
    "publication_requires_draft": ("", "You can publish only a draft Resource."),
    "resource_already_archived": ("", "This Resource is already archived."),
    "download_file_missing": ("file", "This Resource has no attached file."),
    "ordering_invalid": ("ordering", "Choose a Resource order."),
    "audience_invalid": ("audience", "Choose an audience."),
    "category_invalid": ("category", "Choose a category."),
    "kind_invalid": ("kind", "Choose a Resource type."),
    "status_invalid": ("status", "Choose a Resource status."),
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
