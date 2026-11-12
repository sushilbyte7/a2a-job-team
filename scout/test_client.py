"""Scout test client — card discovery + one real find_jobs call.

Run (with scout/server.py running):  python -m scout.test_client
"""

from __future__ import annotations

import asyncio
import json
import sys

import httpx

from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest

BASE_URL = "http://127.0.0.1:10001"
QUERY = sys.argv[1] if len(sys.argv) > 1 else '{"role": "web developer", "location": "Patna"}'


async def main() -> None:
    # One shared client with trust_env=False: localhost must bypass any
    # system proxy vars (httpx otherwise chokes parsing NO_PROXY entries
    # in sandboxed shells). Same gotcha as PLAN.md notes for Day 1.
    async with httpx.AsyncClient(trust_env=False) as httpx_client:
        resolver = A2ACardResolver(httpx_client=httpx_client, base_url=BASE_URL)
        card = await resolver.get_agent_card()

        print(f"Card: {card.name} v{card.version} — {card.description}")
        print(f"Skills: {[s.id for s in card.skills]}")

        message = new_text_message(QUERY, role=Role.ROLE_USER)
        client = await create_client(
            agent=card,
            client_config=ClientConfig(streaming=False, httpx_client=httpx_client),
        )
        async for chunk in client.send_message(SendMessageRequest(message=message)):
            print(chunk)
        await client.close()
    print("\nScout round-trip OK.")


if __name__ == "__main__":
    asyncio.run(main())
