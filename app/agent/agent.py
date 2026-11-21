"""Definizione dell'agente. `root_agent` è il nome che `adk web` cerca."""
import time

import httpx
from google.adk.agents import Agent
from google.adk.models import BaseLlm, FallbackModel, Gemini, LlmRequest
from google.adk.models.anthropic_llm import AnthropicLlm  # non esportato da google.adk.models
from google.genai import types
from pydantic import PrivateAttr

from app.config import (AGENT_FALLBACK_MODELS, AGENT_MODEL, AGENT_PRIMARY_COOLDOWN_S,
                        AGENT_RETRY_ATTEMPTS, AGENT_TIMEOUT_S)
from app.agent.tools import ALL_TOOLS

RETRY_STATUS_CODES = [429, 500, 502, 503, 504]


class _FallbackOnTimeout(FallbackModel):
    """FallbackModel con due aggiunte pensate per la demo:

    1. passa alla riserva anche sui timeout: sul livello gratuito un modello
       sovraccarico può metterci oltre un minuto per rispondere 503;
    2. "appiccicoso": se il principale fallisce, viene saltato per `cooldown_s`
       secondi, così le chiamate successive vanno subito alla riserva.

    È sicuro perché il cambio avviene prima della risposta: nessun tool è stato eseguito.
    """

    cooldown_s: float = 300
    _primary_down_until: float = PrivateAttr(default=0.0)

    def _should_fall_back(self, error: BaseException) -> bool:
        ok = super()._should_fall_back(error) or isinstance(error, (httpx.TimeoutException, TimeoutError))
        if ok:
            # Le riserve si provano solo dopo un fallimento del principale nella stessa
            # chiamata, quindi qualunque fallimento qui implica che il principale è giù.
            self._primary_down_until = time.monotonic() + self.cooldown_s
        return ok

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False):
        if time.monotonic() < self._primary_down_until:
            backups = self.models[1:]
            chain = self._delegate(backups[0]) if len(backups) == 1 else \
                _FallbackOnTimeout(models=backups, cooldown_s=0)
            llm_request.model = chain.model
            async for response in chain.generate_content_async(llm_request, stream):
                yield response
            return
        async for response in super().generate_content_async(llm_request, stream):
            yield response


def build_model(primary: str, fallbacks: list[str], attempts: int, timeout_s: int = 15,
                cooldown_s: float = 300) -> BaseLlm:
    """Ogni modello riprova con backoff sui 429/5xx, con un timeout per richiesta;
    se insiste, passa al successivo (e per `cooldown_s` resta sulla riserva).
    """
    retry = types.HttpRetryOptions(attempts=attempts, initial_delay=1, max_delay=8,
                                   http_status_codes=RETRY_STATUS_CODES)
    http = {"http_options": types.HttpOptions(timeout=timeout_s * 1000)}  # genai vuole millisecondi

    def make(name: str) -> BaseLlm:
        if name.startswith("claude-"):
            # API Anthropic: legge ANTHROPIC_API_KEY dal .env; retry/backoff li fa già l'SDK.
            return AnthropicLlm(model=name, max_tokens=16000)
        return Gemini(model=name, retry_options=retry, client_kwargs=http)

    chain = [make(m) for m in [primary, *fallbacks]]
    return chain[0] if len(chain) == 1 else _FallbackOnTimeout(models=chain, cooldown_s=cooldown_s)

INSTRUCTION = """
Sei un agente operativo che lavora dentro un'azienda.

Metodo:
1. Capisci l'obiettivo dell'utente; se mancano dati essenziali, chiedili.
2. Usa i tool di lettura per raccogliere i fatti PRIMA di concludere: non inventare dati.
3. Quando serve un'azione, usa i tool di azione (ticket, bozza email).
4. Per azioni rischiose o irreversibili usa SEMPRE request_human_approval.
   Finché un'approvazione è in sospeso, bozze e messaggi verso l'esterno NON promettono
   né accettano nulla: dicono che la richiesta è stata ricevuta ed è in valutazione,
   e che seguirà una risposta.
5. Chiudi con un riepilogo breve: cosa hai trovato, cosa hai fatto, cosa resta all'umano.

Rispondi in italiano, in modo conciso.
""".strip()

root_agent = Agent(
    name="agente_operativo",
    model=build_model(AGENT_MODEL, AGENT_FALLBACK_MODELS, AGENT_RETRY_ATTEMPTS, AGENT_TIMEOUT_S,
                      AGENT_PRIMARY_COOLDOWN_S),
    description="Agente aziendale che legge dati, apre ticket e prepara bozze.",
    instruction=INSTRUCTION,
    tools=ALL_TOOLS,
)
