"""MCP server with tool registration using the official mcp Python SDK."""

from __future__ import annotations

import json
import sys
import traceback

from mcp.server import Server
from mcp.types import TextContent, Tool

from specmap.config import _detect_repo_root
from specmap.tools.annotate import annotate
from specmap.tools.check_sync import check_sync
from specmap.tools.get_unmapped import get_unmapped_changes


def create_server() -> Server:
    """Create and configure the MCP server with all tools."""
    server = Server("specmap")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="specmap_annotate",
                description=(
                    "Generate annotations for code changes with spec references. "
                    "Analyzes git diff against the base branch and uses LLM to "
                    "describe what each code region does with inline [N] references "
                    "to spec documents. Creates .specmap/{branch}.json tracking file. "
                    "On subsequent runs, uses diff-based optimization to skip "
                    "unchanged files and shift line numbers mechanically."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_root": {
                            "type": "string",
                            "description": (
                                "Path to the repository root. "
                                "Auto-detected from cwd if not provided."
                            ),
                        },
                        "code_changes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Specific file paths to analyze. "
                                "Auto-detected from git diff if not provided."
                            ),
                        },
                        "spec_files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Specific spec file paths. "
                                "Auto-discovered from repo if not provided."
                            ),
                        },
                        "branch": {
                            "type": "string",
                            "description": "Branch name. Auto-detected if not provided.",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="specmap_check",
                description=(
                    "Verify existing annotations are still valid. Checks that "
                    "annotated line ranges still exist in the code files."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_root": {
                            "type": "string",
                            "description": "Path to the repository root.",
                        },
                        "branch": {
                            "type": "string",
                            "description": "Branch name. Auto-detected if not provided.",
                        },
                        "files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific files to check annotations for.",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="specmap_unmapped",
                description=(
                    "Find code changes without spec coverage. Returns unmapped line ranges "
                    "and per-file/overall coverage percentages. Coverage is calculated as "
                    "lines in annotations with spec refs / total changed lines."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_root": {
                            "type": "string",
                            "description": "Path to the repository root.",
                        },
                        "branch": {
                            "type": "string",
                            "description": "Branch name. Auto-detected if not provided.",
                        },
                        "base_branch": {
                            "type": "string",
                            "description": (
                                "Base branch for diff comparison. "
                                "Auto-detected if not provided."
                            ),
                        },
                        "threshold": {
                            "type": "number",
                            "description": (
                                "Minimum coverage ratio (0.0-1.0). "
                                "Only files below this threshold are reported."
                            ),
                        },
                    },
                    "required": [],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        repo_root = arguments.get("repo_root") or _detect_repo_root()
        if not repo_root:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": "Could not detect repository root. "
                    "Please provide repo_root or run from within a git repository."
                }),
            )]

        try:
            if name == "specmap_annotate":
                result = await annotate(
                    repo_root=repo_root,
                    code_changes=arguments.get("code_changes"),
                    spec_files=arguments.get("spec_files"),
                    branch=arguments.get("branch"),
                )
            elif name == "specmap_check":
                result = await check_sync(
                    repo_root=repo_root,
                    branch=arguments.get("branch"),
                    files=arguments.get("files"),
                )
            elif name == "specmap_unmapped":
                result = await get_unmapped_changes(
                    repo_root=repo_root,
                    branch=arguments.get("branch"),
                    base_branch=arguments.get("base_branch"),
                    threshold=arguments.get("threshold"),
                )
            else:
                result = {"error": f"Unknown tool: {name}"}

        except Exception as e:
            print(f"[specmap] Error in {name}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            result = {"error": str(e)}

        return [TextContent(type="text", text=json.dumps(result, default=str))]

    return server
