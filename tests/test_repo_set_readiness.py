"""Tests for repo-set acceptance readiness gating (offline)."""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ["VANGUARSTEW_OFFLINE"] = "1"

from benchmark.repo_set import (  # noqa: E402
    CURATED_REPO_SET,
    EXAMPLE_REPO_SET,
    RepoSet,
    load_repo_set,
    validate_repo_set,
)
from benchmark.repo_set_readiness import (  # noqa: E402
    check_readiness,
    failed_checks,
    readiness_headline,
)

_VALID_REPO = {
    "name": "t",
    "source": "https://github.com/pypa/hatch",
    "tier": "recent",
    "held_out": False,
    "freeze_window": {"after": "2025-01-01", "recent_bias": True},
}


def _config(repos):
    return {"name": "test", "repos": repos}


def test_curated_passes_readiness():
    result = check_readiness(load_repo_set(CURATED_REPO_SET))
    assert result["passed"] is True
    assert failed_checks(result) == []


def test_example_fails_on_placeholder_sources():
    result = check_readiness(load_repo_set(EXAMPLE_REPO_SET))
    assert result["passed"] is False
    assert "no_placeholder_sources" in failed_checks(result)
    assert result["checks"][0]["passed"] is True  # valid_config still passes


def test_too_few_tuned_repos_fails():
    repos = [
        {**_VALID_REPO, "name": "a", "tier": "recent", "held_out": False},
        {**_VALID_REPO, "name": "b", "source": "https://github.com/pytest-dev/pluggy",
         "tier": "obscure", "held_out": True},
    ]
    result = check_readiness(validate_repo_set(_config(repos)), min_tuned=2, min_held_out=1)
    assert result["passed"] is False
    assert "min_tuned_repos" in failed_checks(result)


def test_too_few_held_out_repos_fails():
    repos = [
        {**_VALID_REPO, "name": "a", "tier": "recent", "held_out": False},
        {**_VALID_REPO, "name": "b", "source": "https://github.com/pytest-dev/pluggy",
         "tier": "obscure", "held_out": False},
    ]
    result = check_readiness(validate_repo_set(_config(repos)), min_tuned=1, min_held_out=1)
    assert result["passed"] is False
    assert "min_held_out_repos" in failed_checks(result)


def test_missing_tier_fails():
    repos = [
        {**_VALID_REPO, "name": "a", "tier": "recent", "held_out": False},
        {**_VALID_REPO, "name": "b", "source": "https://github.com/pytest-dev/pluggy",
         "tier": "recent", "held_out": True},
    ]
    result = check_readiness(validate_repo_set(_config(repos)))
    assert result["passed"] is False
    assert "both_tiers_present" in failed_checks(result)


def test_invalid_config_fails_only_valid_config():
    result = check_readiness({"repos": []})
    assert result["passed"] is False
    assert failed_checks(result) == [
        "valid_config",
        "min_tuned_repos",
        "min_held_out_repos",
        "both_tiers_present",
        "no_placeholder_sources",
    ]


def test_non_dict_config_fails_gracefully():
    for bad in (None, "not a dict", 42, []):
        result = check_readiness(bad)
        assert result["passed"] is False
        assert failed_checks(result)[0] == "valid_config"


def test_accepts_repo_set_instance():
    repo_set = load_repo_set(CURATED_REPO_SET)
    assert isinstance(repo_set, RepoSet)
    assert check_readiness(repo_set)["passed"] is True


def test_check_readiness_does_not_mutate_config():
    data = json.loads(open(CURATED_REPO_SET, encoding="utf-8").read())
    snapshot = json.dumps(data, sort_keys=True)
    check_readiness(data)
    assert json.dumps(data, sort_keys=True) == snapshot


def test_thresholds_are_configurable():
    repos = [
        {**_VALID_REPO, "name": "a", "tier": "recent", "held_out": False},
        {**_VALID_REPO, "name": "b", "source": "https://github.com/kurtmckee/feedparser",
         "tier": "obscure", "held_out": True},
    ]
    repo_set = validate_repo_set(_config(repos))
    assert check_readiness(repo_set, min_tuned=1, min_held_out=1)["passed"] is True
    assert check_readiness(repo_set, min_tuned=2, min_held_out=1)["passed"] is False


def test_readiness_headline():
    assert "PASS" in readiness_headline(check_readiness(load_repo_set(CURATED_REPO_SET)))
    fail = check_readiness(load_repo_set(EXAMPLE_REPO_SET))
    assert "FAIL" in readiness_headline(fail)
    assert "no_placeholder_sources" in readiness_headline(fail)
    assert readiness_headline({}) == "readiness: no checks evaluated"


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "scripts.repo_set_readiness", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_cli_reports_curated_pass():
    proc = _run_cli(CURATED_REPO_SET)
    assert proc.returncode == 0
    assert "readiness: PASS" in proc.stderr


def test_cli_strict_exits_nonzero_on_example():
    proc = _run_cli(EXAMPLE_REPO_SET, "--strict")
    assert proc.returncode == 1
    assert "readiness: FAIL" in proc.stderr


def test_cli_strict_passes_curated():
    proc = _run_cli(CURATED_REPO_SET, "--strict")
    assert proc.returncode == 0


def test_cli_rejects_invalid_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"repos": []}', encoding="utf-8")
    proc = _run_cli(str(bad))
    assert proc.returncode == 1
    assert "non-empty" in proc.stderr.lower() or "repos" in proc.stderr.lower()
