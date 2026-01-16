"""Entry point for running the Planning Agent MCP server."""
import logging
from planning_agent.fastmcp_server import build_fastmcp_server
from planning_agent.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    server = build_fastmcp_server()
    logger.info(f"Starting Planning Agent MCP server on {config.fastmcp_host}:{config.fastmcp_port}")
    server.run()
