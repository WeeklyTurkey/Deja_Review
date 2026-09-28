# Déjà Review

A memory-augmented code review agent. Its value is persistent team memory
through Hindsight: as it accumulates team standards, past review outcomes and
user feedback, its reviews become visibly more aligned with the team. It is
not a generic one-shot LLM reviewer.

## Architecture

```text
pasted code -> recall team memories (Hindsight bank review-<project>)
-> code + context + memories -> LLM structured JSON (LiteLLM)
-> defensive parse + Pydantic validation -> rendered review + memory refs
-> Accept/Reject feedback -> outcome retained -> future reviews improve
```

- `app.py` — Streamlit UI (header, sidebar, review form, results, feedback)
- `reviewer.py` — orchestration: recall -> prompt -> LLM -> parse/validate
- `memory.py` — Hindsight wrapper (`retain` / `recall`, one bank per project)
- `llm.py` — LiteLLM wrapper (`complete`)
- `seed.py` — 10 seed team memories + 5 deterministic demo snippets
- `smoke.py` — Phase 1 end-to-end pipe check
- `demo_cli.py` — terminal demo (seed -> snippets 1-5)

Projects are hardcoded: `payments-service` and `web-app`. Each has its own
Hindsight bank (`review-<project>`); memories never leak between projects.
Raw submitted code is never stored in Hindsight — only conventions, taught
standards, review outcomes and rejected suggestions.

## Requirements

- Python 3.11+
- Hindsight backend already running locally (run by you, not this app)
- Environment variables: `LLM_MODEL`, `META_API_KEY` (or `GEMINI_API_KEY`
  for the Gemini alternative), `HINDSIGHT_API_URL`

## Install

```bash
cd code-review-agent-placeholder
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your values
```

## Start Hindsight

Hindsight runs separately and must be reachable at `HINDSIGHT_API_URL`. Native
setup (no Docker) is installed in `~/.hindsight-env-312` (server 0.10.1):

```bash
export HINDSIGHT_API_LLM_API_KEY=<your-meta-key>
sh ~/.hindsight-env-312/start-hindsight.sh
```

This starts the API at `http://localhost:8888` with Muse (`muse-spark-1.3`)
as its backend LLM for fact extraction on retain. It reuses the existing
`~/.pg0` database, so seeded memories survive the upgrade. Leave that terminal
running while using the app. The previous 0.8.6 install in `~/.hindsight-env`
is kept as a fallback.

## Run the Streamlit app

```bash
source .venv/bin/activate
streamlit run app.py
```

## Run the terminal checks

```bash
source .venv/bin/activate
python smoke.py     # retain -> recall -> one LLM call
python demo_cli.py  # full seeded demo, snippets 1-5
python seed.py payments-service   # load seeds into a project bank only
```

## How persistent memory changes later reviews

Before every review the agent recalls from the current project's bank with two
queries (team conventions + code-derived), and influencing memories are copied
into each comment's `memory_refs`. Accepted outcomes ("Flagged ... accepted")
make repeat violations reference the earlier flag; rejected suggestions
("Rejected suggestion to ... reason: ...") suppress that suggestion in future
reviews; taught standards apply to all later reviews in that project.

## Scope limitations

No authentication, no GitHub/GitLab integration or PR webhooks, no file
upload (paste code only), English only, two hardcoded projects, no extra
database or vector store besides Hindsight, session-only review history.
