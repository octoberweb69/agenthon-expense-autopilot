"""Test della catena di modelli (retry + fallback) senza chiamare il modello."""
import asyncio

import httpx
from google.adk.models import BaseLlm, FallbackModel, Gemini, LlmRequest, LlmResponse
from google.genai import types

from app.agent.agent import _FallbackOnTimeout, build_model


def test_build_model_chain():
    m = build_model("primario", ["riserva-1", "riserva-2"], attempts=4)
    assert isinstance(m, FallbackModel)
    assert [g.model for g in m.models] == ["primario", "riserva-1", "riserva-2"]
    assert all(isinstance(g, Gemini) and g.retry_options.attempts == 4 for g in m.models)
    assert {429, 503} <= set(m.models[0].retry_options.http_status_codes)


def test_timeout_triggers_fallback():
    m = build_model("primario", ["riserva"], attempts=1, timeout_s=15)
    assert m.models[0].client_kwargs["http_options"].timeout == 15_000  # millisecondi
    assert m._should_fall_back(httpx.ReadTimeout("lento"))
    assert not m._should_fall_back(ValueError("bug nostro"))  # i bug non vanno nascosti


class FakeLlm(BaseLlm):
    """Modello finto: conta le chiamate; se `fail`, va in timeout."""
    fail: bool = False
    calls: int = 0

    async def generate_content_async(self, llm_request, stream=False):
        self.calls += 1
        if self.fail:
            raise httpx.ReadTimeout("lento")
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=self.model)]))


async def _ask(m) -> str:
    out = [r async for r in m.generate_content_async(LlmRequest(model=m.model))]
    return out[0].content.parts[0].text


def test_primary_skipped_after_failure():
    primary, backup = FakeLlm(model="primario", fail=True), FakeLlm(model="riserva")
    m = _FallbackOnTimeout(models=[primary, backup], cooldown_s=300)
    assert asyncio.run(_ask(m)) == "riserva"
    assert asyncio.run(_ask(m)) == "riserva"
    assert primary.calls == 1 and backup.calls == 2  # la seconda volta il primario è saltato


def test_primary_retried_after_cooldown():
    primary, backup = FakeLlm(model="primario", fail=True), FakeLlm(model="riserva")
    m = _FallbackOnTimeout(models=[primary, backup], cooldown_s=0)
    asyncio.run(_ask(m))
    primary.fail = False
    assert asyncio.run(_ask(m)) == "primario"  # passato il cooldown si torna al principale


def test_claude_in_chain():
    m = build_model("gemini-x", ["gemini-lite", "claude-opus-5-5"], attempts=1)
    assert [type(x).__name__ for x in m.models] == ["Gemini", "Gemini", "AnthropicLlm"]
    assert m.models[2].model == "claude-opus-5-5"


def test_build_model_without_fallback():
    m = build_model("solo-questo", [], attempts=2)
    assert isinstance(m, Gemini) and m.model == "solo-questo"
