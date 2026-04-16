"""Tests for annotation diff-range filtering in the mapper."""

from __future__ import annotations

from specmap.indexer.mapper import _overlaps_any_range, _convert_results
from specmap.llm.schemas import AnnotationRef, AnnotationResponse, AnnotationResult


def _make_response(*annotations: tuple[str, int, int]) -> AnnotationResponse:
    """Build a minimal AnnotationResponse from (file, start, end) tuples."""
    results = [
        AnnotationResult(
            file=f,
            start_line=s,
            end_line=e,
            description="test",
            refs=[],
            reasoning="test",
        )
        for f, s, e in annotations
    ]
    return AnnotationResponse(annotations=results)


def test_overlaps_any_range_inside():
    """Annotation fully inside a range."""
    assert _overlaps_any_range(5, 10, [(3, 12)]) is True


def test_overlaps_any_range_partial():
    """Annotation partially overlapping."""
    assert _overlaps_any_range(5, 10, [(8, 15)]) is True


def test_overlaps_any_range_boundary():
    """Annotation ending exactly at range start (inclusive)."""
    assert _overlaps_any_range(5, 10, [(10, 15)]) is True


def test_overlaps_any_range_no_overlap():
    """Annotation fully outside all ranges."""
    assert _overlaps_any_range(5, 10, [(11, 15), (20, 25)]) is False


def test_overlaps_any_range_empty():
    """Empty ranges list."""
    assert _overlaps_any_range(5, 10, []) is False


def test_convert_results_filters_outside_diff():
    """Annotations outside diff ranges are dropped."""
    response = _make_response(
        ("file.py", 5, 10),   # outside diff
        ("file.py", 50, 60),  # overlaps diff
    )
    diff_ranges = {"file.py": [(48, 62)]}
    annotations = _convert_results(response, diff_ranges_by_file=diff_ranges)
    assert len(annotations) == 1
    assert annotations[0].start_line == 50


def test_convert_results_no_filter_when_none():
    """When diff_ranges_by_file is None, all annotations pass."""
    response = _make_response(
        ("file.py", 1, 5),
        ("file.py", 100, 200),
    )
    annotations = _convert_results(response, diff_ranges_by_file=None)
    assert len(annotations) == 2


def test_convert_results_file_not_in_ranges():
    """Annotations for files without diff ranges are kept."""
    response = _make_response(
        ("other.py", 1, 5),
    )
    diff_ranges = {"file.py": [(10, 20)]}
    annotations = _convert_results(response, diff_ranges_by_file=diff_ranges)
    assert len(annotations) == 1
