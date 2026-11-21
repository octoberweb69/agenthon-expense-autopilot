"""Esegue l'agente e restituisce risposta + traccia dei tool (utile in demo)."""
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent.agent import root_agent
from app.config import APP_NAME

session_service = InMemorySessionService()
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service,
                auto_create_session=True)


async def chat(message: str, user_id: str, session_id: str) -> dict:
    content = types.Content(role="user", parts=[types.Part(text=message)])
    trace: list[dict] = []
    answer = ""
    models_used: list[str] = []  # quale modello ha risposto: mostra se è scattata la riserva

    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        if event.model_version and event.model_version not in models_used:
            models_used.append(event.model_version)
        for call in event.get_function_calls() or []:
            trace.append({"type": "call", "tool": call.name, "args": dict(call.args or {})})
        for resp in event.get_function_responses() or []:
            trace.append({"type": "result", "tool": resp.name, "result": resp.response})
        if event.is_final_response() and event.content and event.content.parts:
            answer = "".join(p.text or "" for p in event.content.parts)

    return {"answer": answer, "trace": trace, "models": models_used}
