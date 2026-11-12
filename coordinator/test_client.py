"""Coordinator test client — CLI end-to-end demo (Day 4).

Run (with all three servers up — Scout :10001, Scribe :10002,
Coordinator :8000):
  python -m coordinator.test_client [role] [location]
  python -m coordinator.test_client --stream [role] [location]

Default run: POST /run and print jobs + tailored application + trace.
--stream: GET /stream and print each trace event as it arrives.
"""

from __future__ import annotations

import asyncio
import json
import sys

import httpx

BASE_URL = "http://127.0.0.1:8000"


def _print_result(data: dict) -> None:
    result = data.get("result", data)
    print(f"\n=== Trace ({len(data.get('trace', []))} events) ===")
    for evt in data.get("trace", []):
        print(f"  {evt['seq']:>2}. [{evt['agent']}] {evt['event']}")
    if result.get("error"):
        print(f"\nERROR: {result['error']}")
        return
    print(f"\n=== Jobs ({len(result.get('jobs', []))}) ===")
    for job in result.get("jobs", []):
        print(f"  - {job.get('title')} @ {job.get('company')} "
              f"({job.get('location')}, score {job.get('score')})")
    app = result.get("application") or {}
    print(f"\n=== Tailored application ({app.get('model', '')}) ===")
    for bullet in app.get("bullets", []):
        print(f"  * {bullet}")
    print(f"\n  {app.get('cover_note', '')}")


async def _run_post(role: str, location: str) -> None:
    async with httpx.AsyncClient(trust_env=False, timeout=300.0) as client:
        response = await client.post(
            f"{BASE_URL}/run", json={"role": role, "location": location}
        )
        response.raise_for_status()
        _print_result(response.json())
    print("\nCoordinator POST /run OK.")


async def _run_stream(role: str, location: str) -> None:
    async with httpx.AsyncClient(trust_env=False, timeout=300.0) as client:
        async with client.stream(
            "GET", f"{BASE_URL}/stream",
            params={"role": role, "location": location},
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[len("data: "):]
                if payload == "[DONE]":
                    break
                evt = json.loads(payload)
                if evt["event"] == "result":
                    result = evt["detail"]
                    print(f"RESULT: {len(result.get('jobs', []))} jobs, "
                          f"{len((result.get('application') or {}).get('bullets', []))} bullets"
                          + (f", ERROR: {result['error']}" if result.get("error") else ""))
                else:
                    print(f"  {evt['seq']:>2}. [{evt['agent']}] {evt['event']}")
    print("\nCoordinator GET /stream OK.")


async def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    role = args[0] if args else "web developer"
    location = args[1] if len(args) > 1 else "Patna"
    if "--stream" in sys.argv:
        await _run_stream(role, location)
    else:
        await _run_post(role, location)


if __name__ == "__main__":
    asyncio.run(main())
