"""Scribe A2A server — plain Python + Gemini on :10002, skill `tailor_application`.

Run:  python -m scribe.server        (from the repo root)
Card: http://127.0.0.1:10002/.well-known/agent-card.json

Needs GEMINI_API_KEY in .env (see .env.example), or SCRIBE_DRY_RUN=1 for a
no-LLM template tailoring. Send it either JSON
{"title": "Web Developer", "company": "Acme", "location": "Patna"}
or a plain job title.
"""

from __future__ import annotations

import asyncio

import uvicorn
from starlette.applications import Starlette

from a2a.helpers import (
    get_message_text,
    new_task_from_user_message,
    new_text_message,
    new_text_part,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    TaskState,
)

from .agent import parse_request, run_scribe


class ScribeAgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task or new_task_from_user_message(context.message)
        if not context.current_task:
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(
            event_queue=event_queue, task_id=task.id, context_id=task.context_id
        )
        await updater.update_status(
            state=TaskState.TASK_STATE_WORKING,
            message=new_text_message("Scribe is tailoring your application..."),
        )
        try:
            job = parse_request(get_message_text(context.message) or "")
            # run_scribe is sync and the Gemini call takes seconds: keep it
            # off the event loop.
            result = await asyncio.to_thread(run_scribe, job)
            payload = result.model_dump_json(indent=2)
        except Exception as exc:
            payload = f"Scribe failed: {exc}"
        await updater.add_artifact(parts=[new_text_part(text=payload, media_type="application/json")])
        await updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message("Scribe finished."),
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("Cancel not supported in Scribe.")


def build_app() -> Starlette:
    skill = AgentSkill(
        id="tailor_application",
        name="Tailor application",
        description="Writes 3 tailored resume bullets + a short cover note for one job, grounded only in the candidate's real profile. Never invents experience.",
        input_modes=["text/plain"],
        output_modes=["application/json"],
        tags=["a2a", "jobs", "application"],
        examples=[
            '{"title": "Web Developer", "company": "Acme", "location": "Patna"}',
            "Web Developer fresher",
        ],
    )
    public_card = AgentCard(
        name="Scribe",
        description="Plain-Python + Gemini agent that tailors job applications.",
        version="0.1.0",
        default_input_modes=["text/plain"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(streaming=True),
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                url="http://127.0.0.1:10002",
                protocol_version="1.0",
            )
        ],
        skills=[skill],
    )
    handler = DefaultRequestHandler(
        agent_executor=ScribeAgentExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=public_card,
    )
    routes: list = []
    routes.extend(create_agent_card_routes(public_card))
    routes.extend(create_jsonrpc_routes(handler, "/"))
    return Starlette(routes=routes)


if __name__ == "__main__":
    uvicorn.run(build_app(), host="127.0.0.1", port=10002)
