"""Cached API client factories.

Clients are memoized so a process holds one connection pool per provider
rather than one per call site. API keys are read from the environment by the
SDK itself; nothing here reads or holds a key.
"""

from functools import cache

from openai import OpenAI

from config import DEFAULT_MAX_RETRIES


@cache
def get_openai_client() -> OpenAI:
    """Return the process-wide OpenAI client.

    Reads OPENAI_API_KEY from the environment. Run scripts with
    `uv run --env-file .env ...` so the project-local .env is injected.
    """
    return OpenAI(max_retries=DEFAULT_MAX_RETRIES)
