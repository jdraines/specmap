"""Domain-specific assertion helpers for specmap tests."""

from __future__ import annotations

from harness.cli import CLIResult


# --- Python tool result assertions ---

def assert_map_ok(result: dict) -> None:
    assert result["status"] == "ok", f"Expected status 'ok', got {result['status']!r}"
    assert result["mappings_created"] > 0, "Expected at least one mapping created"


def assert_map_no_changes(result: dict) -> None:
    assert result["status"] in ("no_changes", "no_specs"), f"Unexpected status: {result['status']}"


def assert_coverage(result: dict, expected: float, tolerance: float = 0.01) -> None:
    actual = result["overall_coverage"]
    assert abs(actual - expected) <= tolerance, (
        f"Coverage {actual:.3f} not within {tolerance} of expected {expected:.3f}"
    )


def assert_no_stale(result: dict) -> None:
    stale = result.get("stale", 0)
    assert stale == 0, f"Expected no stale mappings, got {stale}"


def assert_stale_count(result: dict, n: int) -> None:
    stale = result.get("stale", 0)
    assert stale == n, f"Expected {n} stale mappings, got {stale}"


# --- CLI result assertions ---

def assert_pass(cli_result: CLIResult) -> None:
    assert cli_result.returncode == 0, (
        f"Expected exit 0, got {cli_result.returncode}\n"
        f"stdout: {cli_result.stdout}\nstderr: {cli_result.stderr}"
    )


def assert_fail(cli_result: CLIResult) -> None:
    assert cli_result.returncode != 0, (
        f"Expected non-zero exit, got 0\nstdout: {cli_result.stdout}"
    )


def assert_all_valid(cli_result: CLIResult) -> None:
    assert_pass(cli_result)
    assert "hash mismatch" not in cli_result.stdout, (
        f"Found hash mismatch in validate output:\n{cli_result.stdout}"
    )


def assert_check_json_pass(cli_result: CLIResult) -> None:
    assert cli_result.json_data is not None, "No JSON data in check output"
    assert cli_result.json_data["pass"] is True, (
        f"Expected pass=true, got {cli_result.json_data}"
    )


def assert_check_json_fail(cli_result: CLIResult) -> None:
    assert cli_result.json_data is not None, "No JSON data in check output"
    assert cli_result.json_data["pass"] is False, (
        f"Expected pass=false, got {cli_result.json_data}"
    )
