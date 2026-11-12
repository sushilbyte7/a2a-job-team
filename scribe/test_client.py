"""Scribe test client — card discovery + one real tailor_application call.

Run (with scribe/server.py running):  python -m scribe.test_client
Pass a job JSON as the first argument to tailor a different job.
"""

from __future__ import annotations

import asyncio
import sys

import httpx

from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest

BASE_URL = "http://127.0.0.1:10002"
QUERY = (
    sys.argv[1]
    if len(sys.argv) > 1
    else '{"title": "Web Developer (Fresher)", "company": "Indeed listing", '
    '"location": "Patna", "link": "https://www.indeed.com/jobs?q=web+developer+fresher&l=Patna", '
    '"snippet": "21 Web Developer Fresher jobs in Patna. HTML, CSS, JavaScript, React preferred."}'
)


async def main() -> None:
    # Same two gotchas as scout/test_client.py: trust_env=False so localhost
    # bypasses system proxy vars, and a long timeout — a Gemini call with
    # retries can take a minute, far past httpx's 5s default.
    async with httpx.AsyncClient(trust_env=False, timeout=300.0) as httpx_client:
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
    print("\nScribe round-trip OK.")


if __name__ == "__main__":
    asyncio.run(main())
