import asyncio
import os
import json
from planning_agent.config import PlanningConfig
from planning_agent.client.planning_client import PlanningClient

async def test_connection():
    # Load config from mcp.json since it's not in env yet
    with open('mcp.json', 'r') as f:
        mcp_config = json.load(f)
        env = mcp_config['mcpServers']['planning-fastmcp-agent']['env']
    
    config = PlanningConfig(
        PLANNING_URL=env['PLANNING_URL'],
        PLANNING_USERNAME=env['PLANNING_USERNAME'],
        PLANNING_PASSWORD=env['PLANNING_PASSWORD'],
        PLANNING_API_VERSION=env['PLANNING_API_VERSION'],
        PLANNING_MOCK_MODE=False
    )
    
    client = PlanningClient(config)
    try:
        print(f"Connecting to {config.planning_url}...")
        apps = await client.get_applications()
        print("Success!")
        print(json.dumps(apps, indent=2))
    except Exception as e:
        print(f"Failed to connect: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_connection())

