"""Phase 1 pipe check: Hindsight retain -> recall -> one LLM call."""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import llm
import memory

PROJECT = "payments-service"
CONVENTION = "Payments team requires type hints on all public functions."


def main() -> None:
    try:
        memory.retain(PROJECT, CONVENTION)
    except memory.MemoryUnavailable as exc:
        print(f"SMOKE FAILED: Hindsight is unreachable: {exc}")
        raise SystemExit(1)

    try:
        recalled = memory.recall(PROJECT, "What are the team conventions for type hints?")
    except memory.MemoryUnavailable as exc:
        print(f"SMOKE FAILED: Hindsight recall failed: {exc}")
        raise SystemExit(1)

    print("Recalled memories:")
    for text in recalled:
        print(f"  - {text}")
    if not any("type hint" in t.lower() for t in recalled):
        print("SMOKE WARNING: the retained convention was not among recalled memories.")

    try:
        answer = llm.complete(
            system="You are a helpful assistant. Reply in one short sentence.",
            user="What language is this project written in? Reply with one word.",
        )
    except llm.LLMError as exc:
        print(f"SMOKE FAILED: LLM call failed: {exc}")
        raise SystemExit(1)

    print(f"LLM answer: {answer.strip()}")
    print("SMOKE OK")


if __name__ == "__main__":
    main()
