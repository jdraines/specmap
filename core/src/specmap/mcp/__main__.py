import asyncio

from mcp.server.stdio import stdio_server

from specmap.mcp.server import create_server


async def main():
    server = create_server()
    init_options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    asyncio.run(main())
