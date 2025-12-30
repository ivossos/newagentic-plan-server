import asyncio
import base64
import httpx
from planning_agent.config import config

async def check_apps():
    auth_string = f"{config.planning_username}:{config.planning_password}"
    auth_header = base64.b64encode(auth_string.encode()).decode()
    
    url = f"{config.planning_url}/HyperionPlanning/rest/{config.planning_api_version}/applications"
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient(headers=headers) as client:
        print(f"Checking URL: {url}")
        response = await client.get(url)
        print(f"Status: {response.status_code}")
        data = response.json()
        for item in data.get("items", []):
            print(f"App: {item.get('name')} (Type: {item.get('appType')})")

if __name__ == "__main__":
    asyncio.run(check_apps())

