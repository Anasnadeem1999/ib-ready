"""One model, through the course gateway, measured and checked on every call."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from pydantic_ai import Agent  # noqa: E402
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings  # noqa: E402
from pydantic_ai.providers.openai import OpenAIProvider  # noqa: E402
from pydantic_ai.usage import UsageLimits  # noqa: E402

from . import config  # noqa: E402

# Function tools on gpt-6-luna through the gateway's chat endpoint require
# reasoning to be off; with it on, the gateway rejects tool calls (HTTP 400).
SETTINGS = OpenAIChatModelSettings(openai_reasoning_effort="none", temperature=0.2)


class ModelPolicyError(RuntimeError):
    pass


def is_content_filter(exc: BaseException) -> bool:
    """The gateway's provider-side safety filter (Azure prompt shields) rejected the prompt."""
    text = str(exc).lower()
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        text += " " + str(body.get("code", "")).lower()
    return "content_filter" in text or "content management policy" in text


_model: OpenAIChatModel | None = None


def model() -> OpenAIChatModel:
    global _model
    if _model is None:
        src = config.key_source()
        if src is None:
            raise ModelPolicyError(
                "No API key found. Put PORTKEY_API_KEY in a .env file in this folder or the folder above it "
                "(see .env.example)."
            )
        if src == "PORTKEY_API_KEY":
            provider = OpenAIProvider(base_url=config.PORTKEY_BASE_URL, api_key=config.PORTKEY_API_KEY)
        else:
            provider = OpenAIProvider(api_key=config.OPENAI_API_KEY)
        _model = OpenAIChatModel(config.MODEL_NAME, provider=provider)
    return _model


@dataclass
class CallRecord:
    agent: str
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    requests: int
    tool_calls: int
    model_resolved: str | None
    model_ok: bool
    ms: int
    cost_usd: float

    def to_dict(self) -> dict:
        return asdict(self)


def cost_usd(input_tokens: int, cached: int, output: int) -> float:
    p = config.PRICE_PER_M
    uncached = max(input_tokens - cached, 0)
    return (uncached * p["input"] + cached * p["cached_input"] + output * p["output"]) / 1_000_000


def _resolved(result) -> str | None:
    for m in reversed(result.all_messages()):
        name = getattr(m, "model_name", None)
        if name:
            return name
    return None


def model_ok(name: str | None) -> bool:
    return bool(name) and (name == config.MODEL_PREFIX or name.startswith(config.MODEL_PREFIX + "-"))


async def run(agent: Agent, agent_name: str, prompt: str, deps=None, session_id: str | None = None):
    """Run one agent, enforce the request cap, and record exact token usage."""
    t0 = time.perf_counter()
    result = await agent.run(
        prompt, deps=deps, model_settings=SETTINGS,
        usage_limits=UsageLimits(request_limit=config.REQUEST_LIMIT_PER_AGENT),
    )
    u = result.usage
    cached = int(getattr(u, "cache_read_tokens", 0) or 0)
    resolved = _resolved(result)
    rec = CallRecord(
        agent=agent_name, input_tokens=int(u.input_tokens or 0), cached_tokens=cached,
        output_tokens=int(u.output_tokens or 0), requests=int(u.requests or 0),
        tool_calls=int(getattr(u, "tool_calls", 0) or 0), model_resolved=resolved,
        model_ok=model_ok(resolved), ms=int((time.perf_counter() - t0) * 1000),
        cost_usd=0.0,
    )
    rec.cost_usd = round(cost_usd(rec.input_tokens, rec.cached_tokens, rec.output_tokens), 8)
    _log(rec, session_id)
    if not rec.model_ok:
        raise ModelPolicyError(
            f"The gateway answered as {resolved!r}, not {config.MODEL_PREFIX}. Check the model name; this run is void."
        )
    return result, rec


def _log(rec: CallRecord, session_id: str | None) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "session": session_id, **rec.to_dict()}) + "\n")
