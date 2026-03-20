"""Domain-specific assertion helpers for specmap tests."""

from __future__ import annotations

from harness.cli import CLIResult


# --- Python tool result assertions ---

def assert_annotate_ok(result: dict) -> None:
    assert result["status"] == "ok", f"Expected status 'ok', got {result['status']!r}"
    assert result["annotations_created"] > 0, "Expected at least one annotation created"


def assert_annotate_no_changes(result: dict) -> None:
    assert result["status"] in ("no_changes", "no_specs"), f"Unexpected status: {result['status']}"


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
