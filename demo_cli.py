"""Terminal demo: seed -> snippets 1-5 with an outcome retained after snippet 1."""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import memory
import reviewer
import seed

PROJECT = "payments-service"


def _print_result(n: int, result: reviewer.ReviewResult) -> None:
    print(f"\n--- {seed.SNIPPET_TITLES[n]} ---")
    if result.memory_used:
        print(f"{len(result.recalled_memories)} team memories retrieved")
    else:
        print("no team memory used")
    if not result.comments:
        print("No issues found")
        return
    for c in result.comments:
        print(f"[{c.severity}] {c.title}")
        print(f"  explanation: {c.explanation}")
        if c.evidence:
            print(f"  evidence: {c.evidence}")
        for m in c.memory_refs:
            print(f"  memory: {m}")


def main() -> None:
    try:
        count = seed.seed_project(PROJECT)
        print(f"Seeded {count} team memories into '{PROJECT}'.")
    except memory.MemoryUnavailable as exc:
        print(f"WARNING: {exc} Continuing with no team memory used.")

    for n in (1, 2, 3, 4, 5):
        code = seed.get_snippet(n)
        try:
            result = reviewer.review(PROJECT, code)
        except reviewer.ReviewError as exc:
            print(f"\n--- {seed.SNIPPET_TITLES[n]} ---\nREVIEW FAILED: {exc}")
            continue
        except ValueError as exc:
            print(f"\n--- {seed.SNIPPET_TITLES[n]} ---\nREVIEW FAILED: {exc}")
            continue
        _print_result(n, result)
        if n == 1 and result.comments:
            try:
                memory.retain(
                    PROJECT,
                    f"Flagged missing type hints in {seed.SNIPPET_FILES[1]}; accepted.",
                )
            except memory.MemoryUnavailable as exc:
                print(f"WARNING: could not retain outcome: {exc}")


if __name__ == "__main__":
    main()
