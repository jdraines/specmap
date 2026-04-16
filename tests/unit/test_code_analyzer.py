"""Tests for the code analyzer / diff parser."""

from __future__ import annotations

from specmap.indexer.code_analyzer import CodeAnalyzer, parse_patch_ranges


def test_parse_diff_new_file(sample_diff: str):
    """Parsing a diff for a new file should return changes."""
    analyzer = CodeAnalyzer()
    changes = analyzer.parse_diff(sample_diff)

    assert len(changes) >= 1
    assert changes[0].file_path == "api/internal/auth/session.go"
    assert changes[0].change_type == "added"
    assert changes[0].start_line == 1
    assert changes[0].end_line == 31
    assert "SessionStore" in changes[0].content
    assert changes[0].diff_ranges == [(1, 31)]


def test_parse_diff_modified_file():
    """Parsing a diff for a modified file."""
    diff = """\
diff --git a/main.go b/main.go
index 1234567..abcdefg 100644
--- a/main.go
+++ b/main.go
@@ -10,2 +10,4 @@ func main() {
     fmt.Println("hello")
+    fmt.Println("new line 1")
+    fmt.Println("new line 2")
     fmt.Println("world")
"""
    analyzer = CodeAnalyzer()
    changes = analyzer.parse_diff(diff)

    assert len(changes) >= 1
    change = changes[0]
    assert change.file_path == "main.go"
    assert change.change_type == "modified"
    assert change.start_line == 11
    assert change.end_line == 12
    assert "new line 1" in change.content
    assert change.diff_ranges == [(11, 12)]


def test_parse_empty_diff():
    """Empty diff should return no changes."""
    analyzer = CodeAnalyzer()
    changes = analyzer.parse_diff("")
    assert changes == []


def test_parse_invalid_diff():
    """Invalid diff text should return empty list."""
    analyzer = CodeAnalyzer()
    changes = analyzer.parse_diff("not a diff")
    assert changes == []


def test_group_changes():
    """group_changes should group by file path."""
    analyzer = CodeAnalyzer()
    diff = """\
diff --git a/a.go b/a.go
index 1234567..abcdefg 100644
--- a/a.go
+++ b/a.go
@@ -1,3 +1,4 @@
 line1
+added1
 line2
 line3
diff --git a/b.go b/b.go
index 1234567..abcdefg 100644
--- a/b.go
+++ b/b.go
@@ -1,3 +1,4 @@
 line1
+added2
 line2
 line3
"""
    changes = analyzer.parse_diff(diff)
    grouped = analyzer.group_changes(changes)
    assert "a.go" in grouped
    assert "b.go" in grouped


def test_get_file_content(tmp_repo):
    """get_file_content reads file from repo."""
    analyzer = CodeAnalyzer()
    content = analyzer.get_file_content(str(tmp_repo), "docs/auth-spec.md")
    assert content is not None
    assert "Authentication" in content


def test_get_file_content_missing(tmp_repo):
    """get_file_content returns None for missing file."""
    analyzer = CodeAnalyzer()
    content = analyzer.get_file_content(str(tmp_repo), "nonexistent.go")
    assert content is None


# --- parse_patch_ranges tests ---


def test_parse_patch_ranges_basic():
    """GitHub-style patch (no file headers) with added lines."""
    # Lines must use proper unified diff format: ' ' for context, '+' for added
    patch = (
        "@@ -10,3 +10,5 @@ func main() {\n"
        " context\n"
        "+added1\n"
        "+added2\n"
        " context\n"
        " context\n"
    )
    ranges = parse_patch_ranges(patch)
    assert ranges == [(11, 12)]


def test_parse_patch_ranges_multiple_hunks():
    """Patch with multiple hunks produces multiple ranges."""
    patch = (
        "@@ -5,3 +5,4 @@\n"
        " context\n"
        "+added1\n"
        " context\n"
        " context\n"
        "@@ -20,3 +22,5 @@\n"
        " context\n"
        "+added2\n"
        "+added3\n"
        " context\n"
        " context\n"
    )
    ranges = parse_patch_ranges(patch)
    assert len(ranges) == 2
    assert ranges[0] == (6, 6)
    assert ranges[1] == (23, 24)


def test_parse_patch_ranges_new_file():
    """Patch for a new file (all added lines)."""
    patch = (
        "@@ -0,0 +1,3 @@\n"
        "+line1\n"
        "+line2\n"
        "+line3\n"
    )
    ranges = parse_patch_ranges(patch)
    assert ranges == [(1, 3)]


def test_parse_patch_ranges_pure_deletion():
    """Patch with only removed lines returns target insertion point."""
    patch = (
        "@@ -10,4 +10,2 @@\n"
        " context\n"
        "-removed1\n"
        "-removed2\n"
        " context\n"
    )
    ranges = parse_patch_ranges(patch)
    assert len(ranges) == 1
    assert ranges[0] == (10, 10)


def test_parse_patch_ranges_empty():
    """Empty patch returns empty list."""
    assert parse_patch_ranges("") == []
    assert parse_patch_ranges("   ") == []


def test_parse_patch_ranges_malformed():
    """Malformed patch returns empty list."""
    assert parse_patch_ranges("not a patch at all") == []
