"""Day 1: A2A test client — card discovery + non-streaming + streaming send.

Run (with echo_server.py running):  python day1-hello/echo_client.py
"""

import asyncio

import httpx

from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest

BASE_URL = "http://127.0.0.1:9999"
QUERY = "Hello, agent team!"


async def main() -> None:
    # trust_env=False: ignore system proxy vars for localhost work.
    async with httpx.AsyncClient(trust_env=False) as httpx_client:
        resolver = A2ACardResolver(httpx_client=httpx_client, base_url=BASE_URL)
        card = await resolver.get_agent_card()

    print(f"Card: {card.name} v{card.version} — {card.description}")
    print(f"Skills: {[s.id for s in card.skills]}")

    message = new_text_message(QUERY, role=Role.ROLE_USER)
    request = SendMessageRequest(message=message)

    print("\n--- Non-streaming call ---")
    client = await create_client(agent=card, client_config=ClientConfig(streaming=False))
    async for chunk in client.send_message(request):
        print(chunk)
    await client.close()

    print("\n--- Streaming call ---")
    streaming_client = await create_client(
        agent=card, client_config=ClientConfig(streaming=True)
    )
    async for chunk in streaming_client.send_message(request):
        print(chunk)
    await streaming_client.close()

    print("\nDay 1 round-trip OK.")


if __name__ == "__main__":
    asyncio.run(main())
