"""CLI: gate a repo-set config on acceptance-readiness criteria.

  python -m scripts.repo_set_readiness benchmark/repo_sets/curated.json
  python -m scripts.repo_set_readiness benchmark/repo_sets/example.json --strict

With ``--strict`` the process exits non-zero when the readiness checks fail, so an acceptance
run can be gated on its inputs before it starts.
"""

from __future__ import annotations

import argparse
import json
import sys

from benchmark.repo_set import RepoSetError, load_repo_set
from benchmark.repo_set_readiness import (
    DEFAULT_MIN_HELD_OUT,
    DEFAULT_MIN_TUNED,
    check_readiness,
    readiness_headline,
)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Gate a repo-set config on leakage-safe acceptance readiness",
    )
    ap.add_argument("config", help="path to a repo-set JSON file")
    ap.add_argument("--min-tuned", type=int, default=DEFAULT_MIN_TUNED,
                    help=f"minimum tuned repos required (default {DEFAULT_MIN_TUNED})")
    ap.add_argument("--min-held-out", type=int, default=DEFAULT_MIN_HELD_OUT,
                    help=f"minimum held-out repos required (default {DEFAULT_MIN_HELD_OUT})")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 when the readiness checks fail (for CI gating)")
    args = ap.parse_args()

    try:
        repo_set = load_repo_set(args.config)
    except RepoSetError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    result = check_readiness(
        repo_set,
        min_tuned=args.min_tuned,
        min_held_out=args.min_held_out,
    )
    print(readiness_headline(result), file=sys.stderr)
    for check in result["checks"]:
        mark = "PASS" if check["passed"] else "FAIL"
        print(f"  [{mark}] {check['name']}: {check['detail']}", file=sys.stderr)

    print(json.dumps(result, indent=2))

    if args.strict and not result["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
