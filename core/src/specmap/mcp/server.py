"""MCP server with tool registration using the official mcp Python SDK."""

from __future__ import annotations

import json
import sys
import traceback

from mcp.server import Server
from mcp.types import TextContent, Tool

from specmap import __version__
from specmap.config import _detect_repo_root
from specmap.tools.annotate import annotate
from specmap.tools.check_sync import check_sync


def create_server() -> Server:
    """Create and configure the MCP server with all tools."""
    server = Server("specmap", version=__version__)

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
                        "context": {
                            "type": "string",
                            "description": (
                                "Development session context that improves annotation quality. "
                                "Include: (1) what problem you're solving and why, "
                                "(2) non-obvious design decisions or trade-offs, "
                                "(3) which spec requirements this change addresses, "
                                "(4) constraints (performance, backward-compat, etc.). "
                                "This is ephemeral and not stored."
                            ),
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": (
                                "If true, run the classification pipeline (diff, hunk parsing, "
                                "hash comparison) but skip LLM calls and do not save changes. "
                                "Returns a preview of what would be regenerated."
                            ),
                            "default": False,
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
                    context=arguments.get("context"),
                    dry_run=arguments.get("dry_run", False),
                )
            elif name == "specmap_check":
                result = await check_sync(
                    repo_root=repo_root,
                    branch=arguments.get("branch"),
                    files=arguments.get("files"),
                )
            else:
                result = {"error": f"Unknown tool: {name}"}

        except Exception as e:
            print(f"[specmap] Error in {name}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            result = {"error": str(e)}

        return [TextContent(type="text", text=json.dumps(result, default=str))]

    return server
