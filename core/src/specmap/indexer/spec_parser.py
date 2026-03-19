"""Parse markdown spec documents into section hierarchy using mistune v3."""

from __future__ import annotations

import mistune

from specmap.indexer.hasher import hash_document, hash_section
from specmap.state.models import SpecDocument, SpecSection


class SpecParser:
    """Parses markdown documents into a SpecDocument with hierarchical sections."""

    def parse(self, content: str, file_path: str) -> SpecDocument:
        """Parse markdown content and extract headings and their hierarchy.

        Returns a SpecDocument with doc_hash and sections dict keyed by
        "Heading1 > Heading2 > Heading3" paths.
        """
        doc_hash = hash_document(content)
        sections: dict[str, SpecSection] = {}

        # Use mistune's AST renderer to walk the document tree
        md = mistune.create_markdown(renderer="ast")
        ast_tokens = md(content)

        # Build line number lookup: for each character offset, what line is it?
        lines = content.split("\n")
        line_starts = _build_line_starts(lines)

        # Extract headings with their levels and positions
        headings = _extract_headings(ast_tokens, content, line_starts)

        # Build sections: each section's content is from the heading to the next
        # heading of same or higher level
        for i, heading in enumerate(headings):
            level = heading["level"]
            heading_line = heading["line"]
            start_offset = heading["offset"]

            # Find end: next heading of same or higher level (lower or equal number)
            end_offset = len(content)
            for j in range(i + 1, len(headings)):
                if headings[j]["level"] <= level:
                    end_offset = headings[j]["offset"]
                    break

            section_content = content[start_offset:end_offset]
            section_h = hash_section(section_content)

            # Build heading_path from ancestor headings
            heading_path = _build_heading_path(headings, i)
            section_key = " > ".join(heading_path)

            sections[section_key] = SpecSection(
                heading_path=heading_path,
                heading_line=heading_line,
                section_hash=section_h,
            )

        return SpecDocument(doc_hash=doc_hash, sections=sections)


def _build_line_starts(lines: list[str]) -> list[int]:
    """Build a list mapping line index (0-based) to character offset of the line start."""
    starts = []
    offset = 0
    for line in lines:
        starts.append(offset)
        offset += len(line) + 1  # +1 for the \n
    return starts


def _find_line_number(offset: int, line_starts: list[int]) -> int:
    """Find the 1-based line number for a given character offset."""
    for i in range(len(line_starts) - 1, -1, -1):
        if offset >= line_starts[i]:
            return i + 1  # 1-based
    return 1


def _extract_headings(
    ast_tokens: list[dict], content: str, line_starts: list[int]
) -> list[dict]:
    """Extract headings from AST tokens with their level, text, line, and offset."""
    headings = []
    lines = content.split("\n")

    for token in ast_tokens:
        if token.get("type") != "heading":
            continue

        level = token.get("attrs", {}).get("level", 1) if "attrs" in token else 1
        # mistune v3: heading level is in token["attrs"]["level"] or token["level"]
        if "attrs" in token and "level" in token["attrs"]:
            level = token["attrs"]["level"]

        # Extract heading text from children
        heading_text = _extract_text(token.get("children", []))

        # Find the heading in the source by scanning lines for markdown headings
        heading_info = _find_heading_in_source(heading_text, level, lines, line_starts, headings)
        if heading_info:
            headings.append({
                "level": level,
                "text": heading_text,
                "line": heading_info["line"],
                "offset": heading_info["offset"],
            })

    return headings


def _extract_text(children: list[dict]) -> str:
    """Recursively extract plain text from AST children."""
    parts = []
    for child in children:
        if child.get("type") == "text":
            parts.append(child.get("raw", child.get("text", "")))
        elif child.get("type") == "codespan":
            parts.append(child.get("raw", child.get("text", "")))
        elif "children" in child:
            parts.append(_extract_text(child["children"]))
    return "".join(parts)


def _find_heading_in_source(
    heading_text: str,
    level: int,
    lines: list[str],
    line_starts: list[int],
    already_found: list[dict],
) -> dict | None:
    """Find the source position of a heading by matching '#' prefix and text."""
    prefix = "#" * level
    already_used_lines = {h["line"] for h in already_found}

    for i, line in enumerate(lines):
        line_num = i + 1  # 1-based
        if line_num in already_used_lines:
            continue

        stripped = line.strip()
        # ATX heading: starts with '#' * level followed by space and text
        if stripped.startswith(prefix) and not stripped.startswith(prefix + "#"):
            after_hashes = stripped[len(prefix) :].strip()
            # Remove trailing '#' markers
            after_hashes = after_hashes.rstrip("#").strip()
            if after_hashes == heading_text:
                return {
                    "line": line_num,
                    "offset": line_starts[i] if i < len(line_starts) else 0,
                }

    return None


def _build_heading_path(headings: list[dict], index: int) -> list[str]:
    """Build the full heading path for a heading by finding its ancestors."""
    target = headings[index]
    path = [target["text"]]
    current_level = target["level"]

    # Walk backwards to find parent headings
    for i in range(index - 1, -1, -1):
        if headings[i]["level"] < current_level:
            path.insert(0, headings[i]["text"])
            current_level = headings[i]["level"]

    return path
