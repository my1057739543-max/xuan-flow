"""Test Gateway API endpoints."""

import asyncio
import httpx
import sys

async def main():
    print("Testing Gateway API...")
    
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        try:
            r = await client.get("/health")
            print(f"Health: {r.status_code} - {r.text}")
            
            r = await client.get("/api/management/config")
            print(f"Config: {r.status_code} - Config loaded successfully" if r.status_code == 200 else f"Config failed: {r.text}")
            
            r = await client.get("/api/management/tools")
            print(f"Tools: {r.status_code} - Tools loaded successfully" if r.status_code == 200 else f"Tools failed: {r.text}")

            r = await client.get("/api/management/skills")
            print(f"Skills: {r.status_code} - {r.text}")

        except httpx.ConnectError:
            print("❌ Connection failed. Ensure the server is running with 'python run_api.py' in another terminal.")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
