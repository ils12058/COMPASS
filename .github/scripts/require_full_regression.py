#!/usr/bin/env python3
"""Refuse deployment unless Backend full regression succeeded for the exact commit.

Usage: require_full_regression.py --repo OWNER/NAME --sha FULL_SHA
Needs the GitHub CLI (``gh``) authenticated with Actions read access.

Only a completed run of backend-full.yml whose head_sha equals the commit counts, and only if
its conclusion is success. Runs for other commits (an older staging revision or a pull-request
head), running runs, and failed or cancelled runs never satisfy the gate.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

WORKFLOW_FILE = "backend-full.yml"
WORKFLOW_NAME = "Backend full regression"


def fetch_runs(repo: str, sha: str) -> list[dict]:
    output = subprocess.run(
        [
            "gh",
            "api",
            "--method",
            "GET",
            f"repos/{repo}/actions/workflows/{WORKFLOW_FILE}/runs",
            "-f",
            f"head_sha={sha}",
            "-f",
            "per_page=100",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(output).get("workflow_runs", [])


def passing_runs(runs: list[dict], sha: str) -> list[dict]:
    return [
        run
        for run in runs
        if run.get("head_sha") == sha
        and run.get("path", "").endswith(f".github/workflows/{WORKFLOW_FILE}")
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args(argv)
    sha = args.sha.lower()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        print("--sha must be a full 40-character commit SHA.", file=sys.stderr)
        return 2

    runs = fetch_runs(args.repo, sha)
    passed = passing_runs(runs, sha)
    if passed:
        run = max(passed, key=lambda item: item.get("updated_at", ""))
        print(f"{WORKFLOW_NAME} succeeded for {sha}: {run.get('html_url')}")
        return 0

    for run in runs:
        print(
            f"  seen: run {run.get('id')} status={run.get('status')} "
            f"conclusion={run.get('conclusion')} head_sha={run.get('head_sha')}",
            file=sys.stderr,
        )
    print(
        f"{WORKFLOW_NAME} has not completed successfully for {sha}. Deployment is blocked "
        "until it succeeds for the exact staging revision.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
