"""Day 1: minimal A2A echo server (a2a-sdk 1.x, official tutorial pattern).

Run:  python day1-hello/echo_server.py
Card: http://127.0.0.1:9999/.well-known/agent-card.json
"""

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


class EchoAgent:
    """Business logic: just echoes back with a greeting."""

    async def invoke(self, user_request: str) -> str:
        return f"Hello! I received your request ({user_request})"


class EchoAgentExecutor(AgentExecutor):
    def __init__(self) -> None:
        self.agent = EchoAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        if context.current_task:
            task = context.current_task
        else:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(
            event_queue=event_queue, task_id=task.id, context_id=task.context_id
        )
        await updater.update_status(
            state=TaskState.TASK_STATE_WORKING,
            message=new_text_message("Processing request..."),
        )

        query = get_message_text(context.message)
        result = await self.agent.invoke(query) if query else "No text input provided!"

        await updater.add_artifact(parts=[new_text_part(text=result, media_type="text/plain")])
        print("Result:", result)
        await updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message("Request is completed!"),
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("Cancel not supported in the echo agent.")


def build_app() -> Starlette:
    skill = AgentSkill(
        id="echo_bot",
        name="Echo Bot",
        description="Acknowledges the request and replies with a greeting.",
        input_modes=["text/plain"],
        output_modes=["text/plain"],
        tags=["a2a", "echo-example"],
        examples=["hi", "how are you"],
    )

    public_card = AgentCard(
        name="Echo Agent",
        description="Day 1 hello-world A2A agent.",
        version="0.0.1",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                url="http://127.0.0.1:9999",
                protocol_version="1.0",
            )
        ],
        skills=[skill],
    )

    handler = DefaultRequestHandler(
        agent_executor=EchoAgentExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=public_card,
    )

    routes = []
    routes.extend(create_agent_card_routes(public_card))
    routes.extend(create_jsonrpc_routes(handler, "/"))
    return Starlette(routes=routes)


if __name__ == "__main__":
    uvicorn.run(build_app(), host="127.0.0.1", port=9999)
