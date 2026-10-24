"""Settings, key loading, prices and safety limits, all in one place."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parents[1]

# The teaching staff keep their .env one folder above the cloned repo, so look
# in the repo first and then its parent. The first NON-EMPTY value wins, and a
# real environment variable always wins. (load_dotenv(override=False) would let
# an empty `PORTKEY_API_KEY=` copied from .env.example mask the real key above.)
ENV_FILES = [REPO_ROOT / ".env", REPO_ROOT.parent / ".env"]


def load_env(files: list[Path]) -> None:
    for f in files:
        if not f.exists():
            continue
        for k, v in dotenv_values(f).items():
            if v and not os.environ.get(k):
                os.environ[k] = v


load_env(ENV_FILES)

# ---------------------------------------------------------------- product name (rename in one place)
APP_NAME = os.environ.get("APP_NAME", "IB Ready")
APP_TAGLINE = os.environ.get("APP_TAGLINE", "Practice IB interviews. Learn why. Get a plan.")

DATA_DIR = Path(os.environ.get("IBREADY_DATA_DIR", REPO_ROOT / "data"))
DB_PATH = DATA_DIR / "ibready.db"
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
SESSION_TOKEN_BUDGET = int(os.environ.get("IBREADY_SESSION_TOKENS", 120_000))
DAILY_PROFILE_TOKEN_BUDGET = int(os.environ.get("IBREADY_DAILY_PROFILE_TOKENS", 600_000))
DAILY_GLOBAL_TOKEN_BUDGET = int(os.environ.get("IBREADY_DAILY_GLOBAL_TOKENS", 5_000_000))
MIN_SECONDS_BETWEEN_TURNS = 1.0  # basic rate limit per session
MAX_TURNS_PER_SESSION = 80
SIGNIN_PER_IP_PER_MINUTE = int(os.environ.get("IBREADY_SIGNIN_PER_MIN", 20))     # sign-in attempts per client IP
SIGNUPS_PER_IP_PER_HOUR = int(os.environ.get("IBREADY_SIGNUPS_PER_HOUR", 30))    # new profiles per client IP
# (generous on purpose: a class on campus Wi-Fi can share one public IP)
LLM_TIMEOUT_SECONDS = float(os.environ.get("IBREADY_LLM_TIMEOUT", 45))  # per model request; the SDK default is 600 s
