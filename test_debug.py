"""Quick debug test for export_data_slice."""

import asyncio
import json
import sys
from planning_agent.client.planning_client import PlanningClient
from planning_agent.config import load_config

async def test():
    config = load_config()
    client = PlanningClient(config)
    
    # Initialize
    apps = await client.get_applications()
    print(f"Connected to: {apps.get('items', [{}])[0].get('name', 'Unknown')}")
    
    # Test grid - exact format from WORKING_FORMAT_DOCUMENTED.md
    grid = {
        "suppressMissingBlocks": True,
        "pov": {
            "members": [
                ["E501"],
                ["Forecast"],
                ["FY25"],
                ["Final"],
                ["USD"],
                ["No Future1"],
                ["CC9999"],
                ["R131"]
            ]
        },
        "columns": [
            {
                "dimensions": ["Period"],
                "members": [["Dec"]]
            }
        ],
        "rows": [
            {
                "dimensions": ["Account"],
                "members": [["410000"]]
            }
        ]
    }
    
    print("\nSending grid:")
    print(json.dumps({"gridDefinition": grid}, indent=2))
    
    try:
        result = await client.export_data_slice("PlanApp", "FinPlan", grid)
        print("\n[SUCCESS]")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"\n[ERROR]: {e}")
        if hasattr(e, 'response'):
            print(f"Status: {e.response.status_code}")
            try:
                text = e.response.text
                print(f"Response: {text[:1000]}")
            except:
                pass
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(test())
