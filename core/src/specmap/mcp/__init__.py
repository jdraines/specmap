"""Specmap MCP server."""

import asyncio

from mcp.server.stdio import stdio_server

from specmap.mcp.server import create_server


def main() -> None:
    """Entry point for the specmap-mcp console script."""
    asyncio.run(_run())


async def _run() -> None:
    server = create_server()
    init_options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, init_options)
