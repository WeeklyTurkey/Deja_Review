"""LiteLLM wrapper for the review LLM call."""

from __future__ import annotations

import os


class LLMError(Exception):
    """Raised when the LLM call fails."""


# A review is at most 6 short comments; cap output well above that so the
# model can never ramble into thousands of tokens on a small snippet.
MAX_OUTPUT_TOKENS = 1500

# Reasoning effort for providers that support it (Muse: minimal/low/medium/
# high/xhigh/max). Short structured reviews need little reasoning, so default
# to minimal to keep hidden reasoning tokens down. Override with REASONING_EFFORT.
DEFAULT_REASONING_EFFORT = "minimal"
VALID_EFFORTS = ("minimal", "low", "medium", "high", "xhigh", "max")

# Info about the most recent call: model id sent plus token usage reported
# by the provider. Lets callers (and the UI) show what was actually used.
last_call: dict = {}


def get_last_usage() -> dict:
    """Return info about the most recent call (empty dict if none yet)."""
    return dict(last_call)


def complete(system: str, user: str, max_tokens: int = MAX_OUTPUT_TOKENS) -> str:
    """Call the configured model and return the raw text response."""
    try:
        import litellm
    except ImportError as exc:
        raise LLMError(
            "litellm is not installed. Run: pip install -r requirements.txt"
        ) from exc
    model = os.environ.get("LLM_MODEL", "").strip()
    if not model:
        raise LLMError("LLM_MODEL is not set.")
    if model.startswith("meta/"):
        # Muse via the Meta Model API (OpenAI-compatible, https://api.meta.ai/v1).
        key = os.environ.get("META_API_KEY", "").strip()
        if not key:
            raise LLMError("META_API_KEY is not set.")
    else:
        if "/" not in model:
            # Bare names (e.g. "gemini-2.0-flash") route to Vertex AI, which needs
            # Google Cloud credentials. Prefix with "gemini/" so the call goes to
            # Google AI Studio using GEMINI_API_KEY instead.
            model = f"gemini/{model}"
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise LLMError("GEMINI_API_KEY is not set.")
    effort = os.environ.get("REASONING_EFFORT", DEFAULT_REASONING_EFFORT).strip().lower()
    if effort not in VALID_EFFORTS:
        raise LLMError(
            f"REASONING_EFFORT must be one of {', '.join(VALID_EFFORTS)}; got '{effort}'."
        )
    extra: dict = {}
    if model.startswith("meta/"):
        # Forwarded in the request body to the Meta API (verified: LiteLLM
        # lists reasoning_effort as supported for meta/muse-spark models).
        extra["reasoning_effort"] = effort
    try:
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
            api_key=key,
            max_tokens=max_tokens,
            **extra,
        )
    except Exception as exc:
        raise LLMError(f"LLM call failed: {exc}") from exc
    try:
        text = response.choices[0].message.content or ""
    except Exception as exc:
        raise LLMError(f"LLM returned an unexpected response shape: {exc}") from exc
    usage = getattr(response, "usage", None)
    last_call.clear()
    last_call.update(
        {
            "model": model,
            "effort": effort if model.startswith("meta/") else "",
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        }
    )
    print(
        f"[llm] model={model} "
        f"prompt_tokens={last_call['prompt_tokens']} "
        f"completion_tokens={last_call['completion_tokens']}"
    )
    return text
