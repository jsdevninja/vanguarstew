"""Gate whether a repo-set config is ready for a leakage-safe acceptance run.

``validate_repo_set`` checks that a config is *well-formed*; this module checks the orthogonal
question: is a well-formed set actually **adequate** to run M3/M4 generalization on? Too few
tuned or held-out repos, a missing leakage tier, or leftover ``OWNER/...`` placeholder sources
each fail a named check. Pure evaluation — no I/O, never mutates the config, and malformed
input fails ``valid_config`` rather than raising.
"""

from __future__ import annotations

from benchmark.repo_set import TIERS, RepoSet, RepoSetError, validate_repo_set

DEFAULT_MIN_TUNED = 2
DEFAULT_MIN_HELD_OUT = 1

_PLACEHOLDER_NEEDLE = "OWNER/"


def _is_placeholder_source(source: str) -> bool:
    return _PLACEHOLDER_NEEDLE in source


def check_readiness(
    config,
    min_tuned: int = DEFAULT_MIN_TUNED,
    min_held_out: int = DEFAULT_MIN_HELD_OUT,
) -> dict:
    """Evaluate a repo-set config against acceptance-readiness criteria.

    ``config`` may be a parsed JSON object or a :class:`RepoSet`. Returns
    ``{"passed": bool, "checks": [{"name", "passed", "detail"}], "min_tuned", "min_held_out}``.
    """
    checks = []

    def add(name, passed, detail):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    repo_set = None
    try:
        if isinstance(config, RepoSet):
            repo_set = config
            valid = True
        else:
            repo_set = validate_repo_set(config)
            valid = True
    except (RepoSetError, TypeError, ValueError):
        valid = False

    add(
        "valid_config",
        valid,
        "repo-set config is well-formed"
        if valid
        else "repo-set config is invalid or not a JSON object",
    )

    if repo_set is None:
        add("min_tuned_repos", False, "config invalid")
        add("min_held_out_repos", False, "config invalid")
        add("both_tiers_present", False, "config invalid")
        add("no_placeholder_sources", False, "config invalid")
    else:
        n_tuned = len(repo_set.tuned())
        n_held = len(repo_set.held_out())
        add(
            "min_tuned_repos",
            n_tuned >= min_tuned,
            f"{n_tuned} tuned repo(s) (min {min_tuned})",
        )
        add(
            "min_held_out_repos",
            n_held >= min_held_out,
            f"{n_held} held-out repo(s) (min {min_held_out})",
        )
        tiers = {e.tier for e in repo_set.entries}
        both_tiers = all(t in tiers for t in TIERS)
        add(
            "both_tiers_present",
            both_tiers,
            f"tiers present: {sorted(tiers)} (need {list(TIERS)})"
            if both_tiers
            else f"missing tier(s): {sorted(set(TIERS) - tiers)}",
        )
        placeholders = [e.source for e in repo_set.entries if _is_placeholder_source(e.source)]
        no_placeholders = not placeholders
        add(
            "no_placeholder_sources",
            no_placeholders,
            "no placeholder OWNER/... sources"
            if no_placeholders
            else f"placeholder source(s): {placeholders}",
        )

    return {
        "passed": all(c["passed"] for c in checks),
        "checks": checks,
        "min_tuned": min_tuned,
        "min_held_out": min_held_out,
    }


def failed_checks(result: dict) -> list:
    """The names of the checks that failed in a :func:`check_readiness` result."""
    if not isinstance(result, dict):
        return []
    return [c["name"] for c in result.get("checks", []) if not c.get("passed")]


def readiness_headline(result: dict) -> str:
    """A one-line human summary of a :func:`check_readiness` result."""
    if not isinstance(result, dict):
        return "readiness: no checks evaluated"
    checks = result.get("checks") or []
    if not checks:
        return "readiness: no checks evaluated"
    if result.get("passed"):
        return f"readiness: PASS (all {len(checks)} checks passed)"
    failed = failed_checks(result)
    return f"readiness: FAIL ({len(failed)}/{len(checks)} checks failed: {', '.join(failed)})"
