"""Settings, key loading, prices and safety limits, all in one place."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]

# The teaching staff keep their .env one folder above the cloned repo, so look
# in the repo first and then its parent. load_dotenv never overrides a value
# that is already set, so the repo's own .env wins if both exist.
ENV_FILES = [REPO_ROOT / ".env", REPO_ROOT.parent / ".env"]
for _f in ENV_FILES:
    if _f.exists():
        load_dotenv(_f, override=False)

DATA_DIR = Path(os.environ.get("TICKTIE_DATA_DIR", REPO_ROOT / "data"))
DB_PATH = DATA_DIR / "ticktie.db"
LOG_PATH = DATA_DIR / "llm_calls.jsonl"

# ---------------------------------------------------------------- model
# The course key may only be used with gpt-6-luna. The gateway silently swaps
# in an older model for an unknown name, so the resolved model is checked on
# every call (see llm.py).
MODEL_NAME = "gpt-6-luna"
MODEL_PREFIX = "gpt-6-luna"

PORTKEY_API_KEY = os.environ.get("PORTKEY_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
PORTKEY_BASE_URL = os.environ.get("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")


def key_source() -> str | None:
    if PORTKEY_API_KEY:
        return "PORTKEY_API_KEY"
    if OPENAI_API_KEY:
        return "OPENAI_API_KEY"
    return None


# ---------------------------------------------------------------- prices
# gpt-6-luna list prices, USD per 1M tokens (MGT 409 Lecture 11, "Cached Token
# Cost", from OpenAI's pricing page). The gateway reports cached input tokens
# separately; automatic prompt caching has no separate cache-write charge.
PRICE_PER_M = {"input": 0.10, "cached_input": 0.01, "output": 0.50}

# ---------------------------------------------------------------- limits (safety + cost)
MAX_ANSWER_CHARS = 2000          # longer answers are cut before any model sees them
MAX_FOLLOWUPS_PER_QUESTION = 2   # stop rule: at most two probes per question
MAX_ATTEMPTS_PER_QUESTION = 2    # after two wrong attempts the solution is shown
REQUEST_LIMIT_PER_AGENT = 4      # model requests per agent run (stops tool loops)
SESSION_TOKEN_BUDGET = int(os.environ.get("TICKTIE_SESSION_TOKENS", 120_000))
DAILY_PROFILE_TOKEN_BUDGET = int(os.environ.get("TICKTIE_DAILY_PROFILE_TOKENS", 600_000))
DAILY_GLOBAL_TOKEN_BUDGET = int(os.environ.get("TICKTIE_DAILY_GLOBAL_TOKENS", 5_000_000))
MIN_SECONDS_BETWEEN_TURNS = 1.0  # basic rate limit per session
MAX_TURNS_PER_SESSION = 60
