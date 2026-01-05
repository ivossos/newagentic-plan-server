import logging
import sys

# Configure logging BEFORE any imports that might set up loggers
# For stdio transport, we must suppress all output except JSON-RPC messages
logging.basicConfig(
    level=logging.ERROR,  # Only log errors and above
    stream=sys.stderr,
    format="%(levelname)s: %(message)s"
)

# Suppress noisy loggers from MCP and httpx
for logger_name in ["mcp", "httpx", "httpcore", "asyncio", "uvicorn", "anyio"]:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

from planning_agent.fastmcp_server import build_fastmcp_server


def main() -> None:
    server = build_fastmcp_server()
    server.run("stdio")


if __name__ == "__main__":
    main()

