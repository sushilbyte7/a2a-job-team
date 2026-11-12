"""Scout A2A server — LangGraph agent on :10001, skill `find_jobs`.

Run:  python -m scout.server        (from the repo root)
Card: http://127.0.0.1:10001/.well-known/agent-card.json

Send it either JSON {"role": "web developer", "location": "Patna"}
or plain text like "web developer fresher jobs in Patna".
"""

from __future__ import annotations

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

from .agent import parse_request, run_scout


class ScoutAgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task or new_task_from_user_message(context.message)
        if not context.current_task:
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(
            event_queue=event_queue, task_id=task.id, context_id=task.context_id
        )
        await updater.update_status(
            state=TaskState.TASK_STATE_WORKING,
            message=new_text_message("Scout is searching fresher jobs..."),
        )
        try:
            role, location = parse_request(get_message_text(context.message) or "")
            result = run_scout(role, location, max_results=5)
            payload = result.model_dump_json(indent=2)
        except Exception as exc:
            payload = f"Scout failed: {exc}"
        await updater.add_artifact(parts=[new_text_part(text=payload, media_type="application/json")])
        await updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message("Scout finished."),
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("Cancel not supported in Scout.")


def build_app() -> Starlette:
    skill = AgentSkill(
        id="find_jobs",
        name="Find fresher jobs",
        description="Searches and filters fresher jobs for a role + location, returns structured listings.",
        input_modes=["text/plain"],
        output_modes=["application/json"],
        tags=["a2a", "jobs", "fresher"],
        examples=[
            '{"role": "web developer", "location": "Patna"}',
            "web developer fresher jobs in Patna",
        ],
    )
    public_card = AgentCard(
        name="Scout",
        description="LangGraph agent that finds and filters fresher jobs.",
        version="0.1.0",
        default_input_modes=["text/plain"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(streaming=True),
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                url="http://127.0.0.1:10001",
                protocol_version="1.0",
            )
        ],
        skills=[skill],
    )
    handler = DefaultRequestHandler(
        agent_executor=ScoutAgentExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=public_card,
    )
    routes: list = []
    routes.extend(create_agent_card_routes(public_card))
    routes.extend(create_jsonrpc_routes(handler, "/"))
    return Starlette(routes=routes)


if __name__ == "__main__":
    uvicorn.run(build_app(), host="127.0.0.1", port=10001)
