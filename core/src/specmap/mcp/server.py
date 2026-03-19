"""MCP server with tool registration using the official mcp Python SDK."""

from __future__ import annotations

import json
import sys
import traceback

from mcp.server import Server
from mcp.types import TextContent, Tool

from specmap.config import _detect_repo_root
from specmap.tools.check_sync import check_sync
from specmap.tools.get_unmapped import get_unmapped_changes
from specmap.tools.map_code_to_spec import map_code_to_spec
from specmap.tools.reindex import reindex


def create_server() -> Server:
    """Create and configure the MCP server with all tools."""
    server = Server("specmap")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="specmap_map",
                description=(
                    "Map code changes to spec documents. Analyzes git diff against the base "
                    "branch and uses LLM to identify which spec text describes the intent "
                    "behind each code change. Creates .specmap/{branch}.json tracking file."
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
                    "Verify existing specmap mappings are still valid. Re-computes hashes "
                    "for spec spans and code targets, attempts relocation for mismatches, "
                    "and marks stale mappings."
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
                            "description": "Specific files to check mappings for.",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="specmap_unmapped",
                description=(
                    "Find code changes without spec coverage. Returns unmapped line ranges "
                    "and per-file/overall coverage percentages."
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
            Tool(
                name="specmap_reindex",
                description=(
                    "Selective re-indexing of specmap data. Compares document and section "
                    "hashes to detect changes, relocates spans where possible, and uses "
                    "LLM to re-map stale mappings. Proportional to change size."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_root": {
                            "type": "string",
                            "description": "Path to the repository root.",
                        },
                        "spec_files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific spec files to re-index.",
                        },
                        "code_files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific code files to re-index mappings for.",
                        },
                        "force": {
                            "type": "boolean",
                            "description": "Force re-index everything regardless of hashes.",
                            "default": False,
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
            if name == "specmap_map":
                result = await map_code_to_spec(
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
            elif name == "specmap_reindex":
                result = await reindex(
                    repo_root=repo_root,
                    spec_files=arguments.get("spec_files"),
                    code_files=arguments.get("code_files"),
                    force=arguments.get("force", False),
                )
            else:
                result = {"error": f"Unknown tool: {name}"}

        except Exception as e:
            print(f"[specmap] Error in {name}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            result = {"error": str(e)}

        return [TextContent(type="text", text=json.dumps(result, default=str))]

    return server
