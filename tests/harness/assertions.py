"""Domain-specific assertion helpers for specmap tests."""

from __future__ import annotations

from harness.cli import CLIResult


# --- Python tool result assertions ---

def assert_annotate_ok(result: dict) -> None:
    assert result["status"] == "ok", f"Expected status 'ok', got {result['status']!r}"
    assert result["annotations_created"] > 0, "Expected at least one annotation created"


def assert_annotate_no_changes(result: dict) -> None:
    assert result["status"] in ("no_changes", "no_specs"), f"Unexpected status: {result['status']}"


def assert_coverage(result: dict, expected: float, tolerance: float = 0.01) -> None:
    actual = result["overall_coverage"]
    assert abs(actual - expected) <= tolerance, (
        f"Coverage {actual:.3f} not within {tolerance} of expected {expected:.3f}"
    )


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
    assert "invalid" not in cli_result.stdout.lower() or "0 invalid" in cli_result.stdout.lower(), (
        f"Found invalid annotations in validate output:\n{cli_result.stdout}"
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
