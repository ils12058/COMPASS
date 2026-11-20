"""Selection and byte identity shared by the bounded CSV import endpoints."""

from __future__ import annotations

import csv
import hashlib
import io
from hmac import compare_digest


class CsvSelectionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def file_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_file_hash(data: bytes, file_hash: str | None) -> None:
    if not file_hash:
        raise CsvSelectionError(
            "csv_import_preview_required", "Validate the CSV before importing it."
        )
    if not compare_digest(file_digest(data).encode(), file_hash.encode()):
        raise CsvSelectionError(
            "csv_import_file_mismatch",
            "The CSV file differs from the preview. Validate the file again. Nothing was imported.",
        )


def selected_row_numbers(rows, issues, selected_rows: list[int] | None) -> set[int]:
    available = {row.row_number for row in (*rows, *issues)}
    if selected_rows is None:
        return available
    if (
        len(selected_rows) > len(available)
        or any(type(number) is not int for number in selected_rows)
        or len(set(selected_rows)) != len(selected_rows)
        or not set(selected_rows) <= available
    ):
        raise CsvSelectionError(
            "csv_import_selection_invalid",
            "Choose row numbers from the preview, without duplicates, then try again.",
        )
    return set(selected_rows)


def selection_counts(*, total: int, selected: int, imported: int, skipped: int) -> dict[str, int]:
    return {
        "total_rows": total,
        "selected_count": selected,
        "imported_count": imported,
        "skipped_count": skipped,
        "not_selected_count": total - selected,
    }


def source_payload(report, data: bytes, payload: dict) -> dict:
    """Return the original fields for client-side correction downloads; never persist them."""
    reader = csv.reader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
    headers = next(reader)
    values = {number: fields for number, fields in enumerate(reader, start=2)}
    payload.update(
        file_hash=file_digest(data),
        headers=headers,
        selected_count=len(report.rows),
        not_selected_count=report.total_rows - len(report.rows),
    )
    for row in payload["rows"]:
        row["values"] = values[row["row_number"]]
    return payload
