"""Review orchestration: recall -> prompt/context -> LLM -> parse/validate."""

from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

import llm
import memory

Severity = Literal["Critical", "Major", "Minor", "Suggestion"]

MAX_COMMENTS = 6


class ReviewComment(BaseModel):
    severity: Severity
    title: str
    explanation: str
    suggestion: str | None = None
    evidence: str = ""
    memory_refs: list[str] = Field(default_factory=list)


class ReviewResult(BaseModel):
    comments: list[ReviewComment] = Field(default_factory=list)
    recalled_memories: list[str] = Field(default_factory=list)
    memory_used: bool = False
    model_used: str = ""
    effort_used: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0


class ReviewError(Exception):
    """Raised when a review cannot be completed (e.g. LLM output unusable)."""


def _code_query(code: str, description: str) -> str:
    """Derive a code-focused recall query from the submission."""
    names = re.findall(r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)", code)
    imports = re.findall(r"^\s*(?:import|from)\s+([a-zA-Z0-9_\.]+)", code, re.MULTILINE)
    parts = []
    if description.strip():
        parts.append(description.strip()[:200])
    if names:
        parts.append("functions: " + ", ".join(names[:8]))
    if imports:
        parts.append("imports: " + ", ".join(imports[:8]))
    snippet = " ".join(code.split())[:300]
    parts.append(f"code: {snippet}")
    return " | ".join(parts)


def _recall_all(project: str, code: str, description: str) -> tuple[list[str], bool]:
    """Run both recall queries. Returns (memories, memory_used).

    If Hindsight is unavailable, returns ([], False) so the caller can
    still produce a baseline review labelled "no team memory used".
    """
    seen: set[str] = set()
    memories: list[str] = []
    try:
        convention_hits = memory.recall(
            project, "team coding conventions, style preferences and standards"
        )
        code_hits = memory.recall(project, _code_query(code, description))
    except memory.MemoryUnavailable as exc:
        print(f"[reviewer] Hindsight unavailable, continuing without memory: {exc}")
        return [], False
    for text in convention_hits + code_hits:
        if text not in seen:
            seen.add(text)
            memories.append(text)
    return memories, True


def _build_prompts(
    code: str, description: str, memories: list[str]
) -> tuple[str, str]:
    # Keep the prompt lean: a few short memories are enough context.
    trimmed = [m[:300] for m in memories[:12]]
    if trimmed:
        memory_block = "\n".join(f"- {m}" for m in trimmed)
    else:
        memory_block = "(no team memories available)"
    system = (
        "You are a precise code reviewer for a software team. "
        "Return ONLY valid JSON matching the requested schema. "
        "Do not wrap it in code fences. Do not include chain-of-thought."
    )
    user = f"""Review the submitted Python code across: correctness, team style/readability,
architecture consistency, security, performance, maintainability/testability.
Report only real issues. Returning zero comments for clean code is correct.
Do not force a finding into every category. At most {MAX_COMMENTS} comments,
most important first. Be concise: 1-2 sentences per explanation, short
suggestions, no preamble and no closing remarks.

Team memories (context, not automatic findings; judge relevance yourself):
{memory_block}

How to use the PR description: it scopes the review. If it states constraints,
limits, or intent (e.g. throwaway script, performance-critical path, specific
feature goal), respect them: suppress findings the description rules out and
prioritize what it emphasizes. A finding that contradicts the stated intent
outranks a style nit.

Rules:
- When a recalled team memory influenced a comment, say so in the explanation
  (e.g. "Flagged again: the team requires ... and this was raised in a previous review")
  and copy that memory's EXACT text into memory_refs.
- Do NOT repeat a suggestion the team previously rejected (a memory starting with
  "Rejected suggestion"), unless the issue is Critical.
- evidence must quote the offending line(s) EXACTLY as they appear in the submitted code.
- Never invent issues, evidence, or line numbers. No line numbers at all.

PR description/context: {description.strip() or "(none)"}

Submitted code:
```
{code}
```

Respond with JSON of exactly this shape:
{{"comments": [{{"severity": "Critical|Major|Minor|Suggestion", "title": "...",
"explanation": "...", "suggestion": "... or null",
"evidence": "exact quote from the code", "memory_refs": ["exact memory texts"]}}]}}"""
    return system, user


def _strip_fences(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*(.*)\s*```$", text, re.DOTALL)
    return match.group(1).strip() if match else text


def _parse_comments(raw: str) -> list[ReviewComment]:
    data = json.loads(_strip_fences(raw))
    if isinstance(data, list):
        data = {"comments": data}
    comments = data.get("comments", [])
    if not isinstance(comments, list):
        raise ValueError("LLM output 'comments' is not a list")
    return [ReviewComment.model_validate(c) for c in comments]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


_STOPWORDS = {
    "the", "a", "an", "to", "of", "in", "for", "on", "is", "it", "and",
    "or", "as", "with", "by", "be", "are", "was", "were", "this", "that",
    "from", "at", "suggestion", "rejected", "reason",
}


def _rejection_topics(memories: list[str]) -> list[set[str]]:
    """Word sets describing what each rejected suggestion was about."""
    topics = []
    for m in memories:
        if m.lower().startswith("rejected suggestion"):
            words = {w for w in re.findall(r"[a-z]+", m.lower()) if w not in _STOPWORDS}
            topics.append(words)
    return topics


def _apply_rejections(
    comments: list[ReviewComment], memories: list[str]
) -> list[ReviewComment]:
    """Drop non-Critical comments that repeat a previously rejected suggestion."""
    topics = _rejection_topics(memories)
    if not topics:
        return comments
    kept = []
    for c in comments:
        if c.severity == "Critical":
            kept.append(c)
            continue
        haystack = {w for w in re.findall(r"[a-z]+", (c.title + " " + c.explanation).lower())}
        if any(len(t & haystack) >= 3 for t in topics):
            print(f"[reviewer] dropping comment repeating rejected suggestion: {c.title}")
            continue
        kept.append(c)
    return kept


def review(project: str, code: str, description: str = "") -> ReviewResult:
    """Run the full review loop for one submission."""
    if not (code or "").strip():
        raise ValueError("No code submitted. Paste code before reviewing.")
    description = description or ""

    memories, memory_used = _recall_all(project, code, description)
    system, user = _build_prompts(code, description, memories)

    last_error: Exception | None = None
    comments: list[ReviewComment] | None = None
    for attempt in (1, 2):
        try:
            raw = llm.complete(system, user)
        except llm.LLMError as exc:
            raise ReviewError(f"LLM call failed: {exc}") from exc
        try:
            comments = _parse_comments(raw)
            break
        except (json.JSONDecodeError, ValueError, ValidationError) as exc:
            last_error = exc
            print(f"[reviewer] attempt {attempt}: unparseable LLM output ({exc}); retrying...")
    if comments is None:
        raise ReviewError(
            f"LLM returned unparseable output twice; giving up. Last error: {last_error}"
        )

    # Defensive: drop fabricated evidence and enforce memory_refs honesty.
    code_norm = _norm(code)
    valid: list[ReviewComment] = []
    for c in comments:
        if c.evidence and _norm(c.evidence) not in code_norm:
            print(f"[reviewer] dropping comment with fabricated evidence: {c.title}")
            continue
        c.memory_refs = [m for m in c.memory_refs if m in memories]
        valid.append(c)

    valid = _apply_rejections(valid, memories)
    get_usage = getattr(llm, "get_last_usage", None)
    usage = get_usage() if callable(get_usage) else {}
    return ReviewResult(
        comments=valid[:MAX_COMMENTS],
        recalled_memories=memories,
        memory_used=memory_used,
        model_used=usage.get("model", ""),
        effort_used=usage.get("effort", "") or "",
        prompt_tokens=usage.get("prompt_tokens", 0) or 0,
        completion_tokens=usage.get("completion_tokens", 0) or 0,
    )
