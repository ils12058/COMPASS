#!/usr/bin/env python3
"""Read the immutable SHA tag digest from doctl's JSON output."""

import json
import re
import sys
from pathlib import Path


SHA_TAG = re.compile(r"[0-9a-f]{40}\Z")
IMAGE_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


def existing_digest(payload: object, expected_tag: str) -> str:
    """Return the digest for expected_tag, or empty if that tag is absent.

    doctl v2.0.0 serializes godo.RepositoryTag fields as snake_case JSON. Its
    Go struct uses `omitempty`, so an empty Tag field is omitted entirely.
    Treat only that omitted/empty tag as an untagged record; validate every
    record's shape and digest before deciding whether the requested SHA exists.
    """
    if not SHA_TAG.fullmatch(expected_tag):
        raise ValueError("expected tag must be a full lowercase commit SHA")
    if not isinstance(payload, list):
        raise ValueError("tag response must be a JSON array")

    matches: list[str] = []
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError("tag response contains a non-object record")

        tag = row.get("tag", "")
        if not isinstance(tag, str):
            raise ValueError("tag response contains a non-string tag")

        digest = row.get("manifest_digest")
        if not isinstance(digest, str) or not IMAGE_DIGEST.fullmatch(digest):
            raise ValueError("tag response contains a missing or invalid manifest digest")

        if tag == expected_tag:
            matches.append(digest)

    if len(matches) > 1:
        raise ValueError("tag response contains duplicate entries for the requested SHA")
    return matches[0] if matches else ""


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: read_doctl_tag_digest.py TAGS_JSON EXPECTED_SHA", file=sys.stderr)
        return 2

    try:
        payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        digest = existing_digest(payload, sys.argv[2])
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"invalid DigitalOcean registry tag response: {exc}", file=sys.stderr)
        return 1

    print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
