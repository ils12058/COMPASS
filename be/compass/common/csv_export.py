"""Safe text cells for UTF-8 CSV consumed by spreadsheets."""


def spreadsheet_safe_text(value: object) -> str:
    text = "" if value is None else str(value)
    # CSV quoting does not prevent a spreadsheet from evaluating formulas. Include leading
    # whitespace and tab/newline entry points; preserve the original display text after a quote.
    if text.startswith(("\t", "\r", "\n")) or text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text
