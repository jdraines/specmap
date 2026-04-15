"""Tests for the diff optimizer — hunk classification and line shifting."""

from __future__ import annotations

from datetime import datetime, timezone

from specmap.indexer.diff_optimizer import (
    ClassifiedAnnotations,
    FileHunks,
    Hunk,
    classify_annotations,
    parse_incremental_diff,
    reclassify_for_spec_changes,
    shift_annotations,
)
from specmap.state.models import Annotation, SpecRef


def _ann(file: str, start: int, end: int, ann_id: str = "a_test") -> Annotation:
    """Create a minimal annotation for testing."""
    return Annotation(
        id=ann_id,
        file=file,
        start_line=start,
        end_line=end,
        description="test",
        created_at=datetime(2026, 3, 19, tzinfo=timezone.utc),
    )


def _ann_with_ref(
    file: str, start: int, end: int, spec_file: str, ann_id: str = "a_test"
) -> Annotation:
    """Create an annotation with a spec ref for testing."""
    return Annotation(
        id=ann_id,
        file=file,
        start_line=start,
        end_line=end,
        description="Implements feature. [1]",
        refs=[
            SpecRef(
                id=1,
                spec_file=spec_file,
                heading="Some Heading",
                start_line=5,
                excerpt="Some spec text.",
            ),
        ],
        created_at=datetime(2026, 3, 19, tzinfo=timezone.utc),
    )


class TestParseIncrementalDiff:
    def test_empty_diff(self):
        result = parse_incremental_diff("")
        assert result == {}

    def test_single_file_single_hunk(self):
        diff = """\
diff --git a/src/main.go b/src/main.go
--- a/src/main.go
+++ b/src/main.go
@@ -10,3 +10,5 @@ func main() {
+    added line 1
+    added line 2
"""
        result = parse_incremental_diff(diff)
        assert "src/main.go" in result
        hunks = result["src/main.go"].hunks
        assert len(hunks) == 1
        assert hunks[0].old_start == 10
        assert hunks[0].old_count == 3
        assert hunks[0].new_start == 10
        assert hunks[0].new_count == 5

    def test_multiple_files(self):
        diff = """\
diff --git a/a.go b/a.go
--- a/a.go
+++ b/a.go
@@ -5,2 +5,3 @@ package a
diff --git a/b.go b/b.go
--- a/b.go
+++ b/b.go
@@ -1,4 +1,2 @@ package b
"""
        result = parse_incremental_diff(diff)
        assert "a.go" in result
        assert "b.go" in result

    def test_pure_addition(self):
        diff = """\
diff --git a/new.go b/new.go
new file mode 100644
--- /dev/null
+++ b/new.go
@@ -0,0 +1,5 @@
+package new
"""
        result = parse_incremental_diff(diff)
        assert "new.go" in result
        hunks = result["new.go"].hunks
        assert len(hunks) == 1
        assert hunks[0].old_count == 0
        assert hunks[0].new_count == 5


class TestClassifyAnnotations:
    def test_unchanged_file_kept(self):
        """Annotations for files not in diff are kept."""
        anns = [_ann("unchanged.go", 1, 10)]
        file_hunks: dict[str, FileHunks] = {}
        result = classify_annotations(anns, file_hunks)
        assert len(result.keep) == 1
        assert len(result.shift) == 0
        assert len(result.regenerate) == 0

    def test_overlapping_regenerated(self):
        """Annotation overlapping a hunk is regenerated."""
        anns = [_ann("src/main.go", 5, 15)]
        file_hunks = {
            "src/main.go": FileHunks("src/main.go", [Hunk(10, 3, 10, 5)]),
        }
        result = classify_annotations(anns, file_hunks)
        assert len(result.regenerate) == 1
        assert len(result.keep) == 0
        assert len(result.shift) == 0

    def test_below_hunk_shifted(self):
        """Annotation entirely below a hunk needs shifting."""
        anns = [_ann("src/main.go", 20, 30)]
        file_hunks = {
            "src/main.go": FileHunks("src/main.go", [Hunk(5, 2, 5, 4)]),
        }
        result = classify_annotations(anns, file_hunks)
        assert len(result.shift) == 1
        assert len(result.regenerate) == 0
        assert len(result.keep) == 0

    def test_above_hunk_kept(self):
        """Annotation entirely above a hunk is kept."""
        anns = [_ann("src/main.go", 1, 3)]
        file_hunks = {
            "src/main.go": FileHunks("src/main.go", [Hunk(10, 2, 10, 4)]),
        }
        result = classify_annotations(anns, file_hunks)
        assert len(result.keep) == 1


class TestShiftAnnotations:
    def test_shift_by_positive_delta(self):
        """Annotations shift down when lines are added above."""
        anns = [_ann("src/main.go", 20, 30)]
        file_hunks = {
            "src/main.go": FileHunks("src/main.go", [Hunk(5, 2, 5, 5)]),
        }
        shifted = shift_annotations(anns, file_hunks)
        assert len(shifted) == 1
        # Delta = 5 - 2 = 3
        assert shifted[0].start_line == 23
        assert shifted[0].end_line == 33

    def test_shift_by_negative_delta(self):
        """Annotations shift up when lines are removed above."""
        anns = [_ann("src/main.go", 20, 30)]
        file_hunks = {
            "src/main.go": FileHunks("src/main.go", [Hunk(5, 5, 5, 2)]),
        }
        shifted = shift_annotations(anns, file_hunks)
        assert len(shifted) == 1
        # Delta = 2 - 5 = -3
        assert shifted[0].start_line == 17
        assert shifted[0].end_line == 27

    def test_no_shift_for_unchanged_file(self):
        """Annotations for files not in diff are unchanged."""
        anns = [_ann("other.go", 10, 20)]
        file_hunks: dict[str, FileHunks] = {}
        shifted = shift_annotations(anns, file_hunks)
        assert shifted[0].start_line == 10
        assert shifted[0].end_line == 20

    def test_cumulative_shift_multiple_hunks(self):
        """Multiple hunks above the annotation produce cumulative shift."""
        anns = [_ann("src/main.go", 50, 60)]
        file_hunks = {
            "src/main.go": FileHunks("src/main.go", [
                Hunk(5, 2, 5, 4),   # delta +2
                Hunk(20, 3, 22, 1),  # delta -2
            ]),
        }
        shifted = shift_annotations(anns, file_hunks)
        # Cumulative delta = +2 + (-2) = 0
        assert shifted[0].start_line == 50
        assert shifted[0].end_line == 60

    def test_shift_clamps_to_valid_range(self):
        """Line numbers should not go below 1."""
        anns = [_ann("src/main.go", 2, 3)]
        file_hunks = {
            "src/main.go": FileHunks("src/main.go", [Hunk(1, 10, 1, 1)]),
        }
        shifted = shift_annotations(anns, file_hunks)
        assert shifted[0].start_line >= 1


class TestReclassifyForSpecChanges:
    def test_no_changed_specs_noop(self):
        """Empty changed_spec_files returns classification unchanged."""
        ann = _ann_with_ref("src/main.go", 1, 10, "docs/spec.md", "a_1")
        classified = ClassifiedAnnotations(keep=[ann], shift=[], regenerate=[])
        result = reclassify_for_spec_changes(classified, set())
        assert len(result.keep) == 1
        assert len(result.regenerate) == 0

    def test_keep_moved_to_regenerate(self):
        """Annotation in keep citing a changed spec moves to regenerate."""
        ann = _ann_with_ref("src/main.go", 1, 10, "docs/spec.md", "a_1")
        classified = ClassifiedAnnotations(keep=[ann], shift=[], regenerate=[])
        result = reclassify_for_spec_changes(classified, {"docs/spec.md"})
        assert len(result.keep) == 0
        assert len(result.regenerate) == 1
        assert result.regenerate[0].id == "a_1"

    def test_shift_moved_to_regenerate(self):
        """Annotation in shift citing a changed spec moves to regenerate."""
        ann = _ann_with_ref("src/main.go", 20, 30, "docs/spec.md", "a_2")
        classified = ClassifiedAnnotations(keep=[], shift=[ann], regenerate=[])
        result = reclassify_for_spec_changes(classified, {"docs/spec.md"})
        assert len(result.shift) == 0
        assert len(result.regenerate) == 1

    def test_unrelated_spec_not_affected(self):
        """Annotation citing an unchanged spec stays in keep."""
        ann = _ann_with_ref("src/main.go", 1, 10, "docs/auth.md", "a_3")
        classified = ClassifiedAnnotations(keep=[ann], shift=[], regenerate=[])
        result = reclassify_for_spec_changes(classified, {"docs/api.md"})
        assert len(result.keep) == 1
        assert len(result.regenerate) == 0

    def test_annotation_without_refs_not_affected(self):
        """Annotation with no refs is never moved (nothing to invalidate)."""
        ann = _ann("src/main.go", 1, 10, "a_4")  # no refs
        classified = ClassifiedAnnotations(keep=[ann], shift=[], regenerate=[])
        result = reclassify_for_spec_changes(classified, {"docs/spec.md"})
        assert len(result.keep) == 1
        assert len(result.regenerate) == 0

    def test_mixed_keep_and_shift(self):
        """Both keep and shift annotations citing changed spec are moved."""
        keep_ann = _ann_with_ref("src/a.go", 1, 5, "docs/spec.md", "a_k")
        shift_ann = _ann_with_ref("src/b.go", 20, 30, "docs/spec.md", "a_s")
        unrelated = _ann_with_ref("src/c.go", 1, 5, "docs/other.md", "a_u")
        already_regen = _ann_with_ref("src/d.go", 1, 5, "docs/spec.md", "a_r")

        classified = ClassifiedAnnotations(
            keep=[keep_ann, unrelated],
            shift=[shift_ann],
            regenerate=[already_regen],
        )
        result = reclassify_for_spec_changes(classified, {"docs/spec.md"})
        assert len(result.keep) == 1
        assert result.keep[0].id == "a_u"
        assert len(result.shift) == 0
        assert len(result.regenerate) == 3  # already_regen + keep_ann + shift_ann
        regen_ids = {a.id for a in result.regenerate}
        assert regen_ids == {"a_r", "a_k", "a_s"}
