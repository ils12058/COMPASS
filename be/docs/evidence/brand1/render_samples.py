"""Render the committed synthetic BRAND-1 fixtures without a database or network.

From be/: .venv/bin/python docs/evidence/brand1/render_samples.py --output /tmp/brand1
Requires the normal backend environment and Poppler's pdftoppm on PATH.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, time
from io import BytesIO
from pathlib import Path

DATE_FIELDS = {
    "issued_on",
    "official_receipt_date",
    "graduation_date",
    "report_date",
    "interview_ended_date",
    "referred_on",
    "received_date",
    "date",
}
TIME_FIELDS = {"report_time", "interview_ended_time", "received_time", "time"}


def restore_dates(value):
    if isinstance(value, list):
        return [restore_dates(item) for item in value]
    if isinstance(value, dict):
        restored = {}
        for key, item in value.items():
            if item and key in DATE_FIELDS:
                restored[key] = date.fromisoformat(item)
            elif item and key in TIME_FIELDS:
                restored[key] = time.fromisoformat(item)
            else:
                restored[key] = restore_dates(item)
        return restored
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--no-previews", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    # Test settings contain only ephemeral keys and local test endpoints. Rendering
    # itself does not connect to those services or read production configuration.
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
    import django

    django.setup()
    from pypdf import PdfReader

    from compass.documents.rendering import render_document_pdf

    results = []
    for source in sorted(Path(__file__).with_name("samples").glob("*.json")):
        fixture = restore_dates(json.loads(source.read_text()))
        if "synthetic_report_scenario" in fixture:
            from compass.reports.pdf import build_student_profiling_print_context
            from tests.test_student_profiling_pdf import RENDER_SCENARIOS

            fixture["context"] = build_student_profiling_print_context(
                RENDER_SCENARIOS[fixture["synthetic_report_scenario"]]()
            )
        result = render_document_pdf(fixture["key"], fixture["version"], context=fixture["context"])
        target = args.output / f"{source.stem}.pdf"
        target.write_bytes(result.pdf_bytes)
        pages = PdfReader(BytesIO(result.pdf_bytes)).pages
        assert all(
            abs(float(page.mediabox.width) - 595.28) < 0.8
            and abs(float(page.mediabox.height) - 841.89) < 0.8
            for page in pages
        )
        if fixture["key"] == "individual_inventory":
            assert len(pages) == 3
        for number, page in enumerate(pages, 1):
            text = page.extract_text()
            assert text.count(f"Page {number} of {len(pages)}") == 1
            assert len(page.images) == (1 if fixture["key"] == "foundation_test_no_footer" else 2)
        if not args.no_previews:
            for preview in args.output.glob(f"{source.stem}-*.png"):
                if preview.stem.rsplit("-", 1)[-1].isdigit():
                    preview.unlink()
            subprocess.run(
                ["pdftoppm", "-r", "120", "-png", str(target), str(args.output / source.stem)],
                check=True,
                capture_output=True,
            )
        results.append({"sample": source.stem, "pages": len(pages), "bytes": len(result.pdf_bytes)})
        print(f"{source.stem}: {len(pages)} A4 pages", flush=True)
    (args.output / "manifest.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
