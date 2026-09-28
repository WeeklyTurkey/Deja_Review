"""Hindsight wrapper for persistent team memory.

One memory bank per project: ``bank_id = f"review-{project}"``.
Memories never leak between projects.

Never store raw submitted code here -- only conventions, standards,
review outcomes and rejected suggestions.
"""

from __future__ import annotations

import concurrent.futures
import os
import time

PROJECTS = ("payments-service", "web-app")

# The Meta API backing the server is intermittently slow/unreachable from here
# (connection timeouts that succeed on retry). Retry transient server-side
# failures instead of failing the user's retain/recall on the first 500.
MAX_ATTEMPTS = 3
RETRY_BACKOFFS = (2.0, 5.0)
TRANSIENT_STATUSES = (500, 502, 503, 504)

# The client's sync wrappers drive asyncio with run_until_complete() on the
# calling thread's loop, which raises "event loop is already running" when our
# caller (e.g. Streamlit) already runs a loop in this thread. Run every client
# call on a worker thread, which never has a running loop.
_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="hindsight"
)


def _call(fn, *args, **kwargs):
    return _executor.submit(fn, *args, **kwargs).result()


def _is_transient(exc: Exception) -> bool:
    """True for failures worth retrying: 5xx statuses and connection/timeout errors."""
    if getattr(exc, "status", None) in TRANSIENT_STATUSES:
        return True
    msg = str(exc).lower()
    return any(
        s in msg
        for s in (
            "connection",
            "timed out",
            "timeout",
            "temporarily unavailable",
            "try again",
        )
    )


def _call_with_retry(fn, *args, **kwargs):
    """Run fn on a worker thread, retrying transient failures."""
    last: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return _call(fn, *args, **kwargs)
        except MemoryUnavailable:
            raise
        except Exception as exc:
            last = exc
            if attempt >= MAX_ATTEMPTS or not _is_transient(exc):
                raise
            wait = RETRY_BACKOFFS[min(attempt - 1, len(RETRY_BACKOFFS) - 1)]
            print(f"[memory] transient failure (attempt {attempt}): {exc}; retrying in {wait}s...")
            time.sleep(wait)
    raise last  # pragma: no cover - loop always returns or raises above


class MemoryUnavailable(Exception):
    """Raised when the Hindsight backend cannot be reached."""


def bank_id(project: str) -> str:
    return f"review-{project}"


def _client():
    """Build a Hindsight client from the HINDSIGHT_API_URL env var."""
    try:
        from hindsight_client import Hindsight
    except ImportError as exc:
        raise MemoryUnavailable(
            "hindsight-client is not installed. Run: pip install -r requirements.txt"
        ) from exc
    url = os.environ.get("HINDSIGHT_API_URL", "").strip()
    if not url:
        raise MemoryUnavailable("HINDSIGHT_API_URL is not set.")
    return Hindsight(base_url=url)


def _extract_texts(response) -> list[str]:
    """Pull plain memory strings out of a recall response.

    Handles the official RecallResponse shape (``.results`` of objects
    with ``.text``) as well as plain dict/list fallbacks.
    """
    results = getattr(response, "results", response)
    if isinstance(results, dict):
        results = results.get("results", [])
    texts: list[str] = []
    for item in results or []:
        if isinstance(item, str):
            text = item
        elif isinstance(item, dict):
            text = item.get("text", "")
        else:
            text = getattr(item, "text", "")
        text = (text or "").strip()
        if text:
            texts.append(text)
    return texts


def retain(project: str, text: str) -> None:
    """Retain one memory string in the project's bank.

    Hindsight auto-creates the bank on first retain. Raises
    MemoryUnavailable if the backend cannot be reached.
    """
    text = (text or "").strip()
    if not text:
        return
    bank = bank_id(project)
    print(f"[memory] retain bank={bank} text_len={len(text)}")
    try:
        client = _client()
        _call_with_retry(client.retain, bank_id=bank, content=text)
    except MemoryUnavailable:
        raise
    except Exception as exc:
        raise MemoryUnavailable(f"Hindsight retain failed for bank '{bank}': {exc}") from exc
    print(f"[memory] retain ok bank={bank}")


def recall(project: str, query: str) -> list[str]:
    """Recall relevant memory strings from the project's bank."""
    query = (query or "").strip()
    bank = bank_id(project)
    print(f"[memory] recall bank={bank} query_len={len(query)}")
    try:
        client = _client()
        response = _call_with_retry(client.recall, bank_id=bank, query=query)
    except MemoryUnavailable:
        raise
    except Exception as exc:
        raise MemoryUnavailable(f"Hindsight recall failed for bank '{bank}': {exc}") from exc
    texts = _extract_texts(response)
    print(f"[memory] recall ok bank={bank} results={len(texts)}")
    return texts
