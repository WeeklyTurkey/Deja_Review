"""Streamlit UI: memory-powered code reviews that learn team standards."""

from __future__ import annotations

from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

import streamlit as st

import memory
import reviewer
import seed

st.set_page_config(page_title="Hindsight Code Review", layout="wide")

SEVERITY_COLORS = {
    "Critical": ("#F8D7DA", "#842029"),
    "Major": ("#FFF3CD", "#664D03"),
    "Minor": ("#E2E8F0", "#334155"),
    "Suggestion": ("#E2E8F0", "#334155"),
}

# --- session state ------------------------------------------------------------
if "history" not in st.session_state:
    st.session_state.history = []
if "result" not in st.session_state:
    st.session_state.result = None
if "feedback" not in st.session_state:
    st.session_state.feedback = {}
if "code" not in st.session_state:
    st.session_state.code = ""
if "description" not in st.session_state:
    st.session_state.description = ""

# --- header -------------------------------------------------------------------
st.title("Hindsight Code Review")
st.caption("Memory-powered reviews that learn your team's standards.")
project = st.selectbox("Project", list(memory.PROJECTS), index=0)

# --- sidebar ------------------------------------------------------------------
with st.sidebar:
    st.header("Team knowledge")
    if st.button("Load demo seed"):
        try:
            n = seed.seed_project(project)
            st.success(f"Loaded {n} team memories into {project}.")
        except memory.MemoryUnavailable as exc:
            st.warning(f"Hindsight unavailable: {exc}")

    snippet_choice = st.selectbox(
        "Demo snippet picker",
        ["(none)"] + [f"Snippet {n}: {seed.SNIPPET_TITLES[n]}" for n in range(1, 6)],
    )
    if st.button("Load snippet") and not snippet_choice.startswith("(none)"):
        n = int(snippet_choice.split(":")[0].replace("Snippet ", ""))
        st.session_state.code = seed.get_snippet(n)
        st.session_state.result = None
        st.session_state.feedback = {}
        st.rerun()

    st.header("Teach a standard")
    standard = st.text_input(
        "New team standard",
        placeholder="e.g. We prefer early returns.",
    )
    if st.button("Teach"):
        if not standard.strip():
            st.warning("Type a standard first.")
        else:
            try:
                memory.retain(project, standard.strip())
                st.success("Standard remembered.")
            except memory.MemoryUnavailable as exc:
                st.warning(f"Hindsight unavailable: {exc}")

    st.header("Review history")
    if not st.session_state.history:
        st.caption("No reviews yet this session.")
    for entry in reversed(st.session_state.history):
        with st.expander(f"{entry['title']} ({entry['comments']} comments)"):
            st.caption(entry["timestamp"])
            st.caption(f"Project: {entry['project']}")

# --- main panel ---------------------------------------------------------------
st.header("Submit code")
code = st.text_area("Code", value=st.session_state.code, height=300, key="code_box")
description = st.text_area(
    "PR description / context (optional)",
    value=st.session_state.description,
    height=80,
    key="desc_box",
)

if st.button("Review Code", type="primary"):
    st.session_state.code = code
    st.session_state.description = description
    st.session_state.result = None
    st.session_state.feedback = {}
    if not code.strip():
        st.warning("Paste some code before reviewing.")
    else:
        status = st.status("Retrieving team knowledge...")
        try:
            status.update(label="Analyzing code...")
            result = reviewer.review(project, code, description)
            st.session_state.result = result
            st.session_state.history.append(
                {
                    "title": (description.strip().splitlines() or ["Pasted snippet"])[0][:60],
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "comments": len(result.comments),
                    "project": project,
                }
            )
            status.update(label="Review complete.", state="complete")
        except reviewer.ReviewError as exc:
            status.update(label="Review failed.", state="error")
            st.error(str(exc))
        except ValueError as exc:
            status.update(label="Review failed.", state="error")
            st.warning(str(exc))

# --- results ------------------------------------------------------------------
result = st.session_state.result
if result is not None:
    if result.memory_used:
        st.info(f"{len(result.recalled_memories)} team memories retrieved")
    else:
        st.warning("no team memory used")
    if result.model_used:
        effort = f" (effort: {result.effort_used})" if result.effort_used else ""
        st.caption(
            f"Reviewed with `{result.model_used}`{effort} · "
            f"{result.prompt_tokens} input / {result.completion_tokens} output tokens"
        )

    if not result.comments:
        st.success("No issues found")
    for i, c in enumerate(result.comments):
        bg, fg = SEVERITY_COLORS.get(c.severity, ("#E2E8F0", "#334155"))
        st.markdown(
            f"<span style='background:{bg};color:{fg};"
            f"padding:2px 10px;border-radius:10px;font-size:0.85em;'>"
            f"{c.severity}</span> **{c.title}**",
            unsafe_allow_html=True,
        )
        st.write(c.explanation)
        if c.suggestion:
            st.code(c.suggestion, language="python")
        if c.evidence:
            st.caption(f"Evidence: `{c.evidence}`")
        if c.memory_refs:
            with st.expander("Why this suggestion?"):
                for m in c.memory_refs:
                    st.write(f"- {m}")
        choice = st.radio(
            f"Feedback for comment {i + 1}",
            ["No action", "Accept", "Reject"],
            key=f"fb_{i}",
            horizontal=True,
        )
        reason = ""
        if choice == "Reject":
            reason = st.text_input(
                "Rejection reason (optional)",
                key=f"reason_{i}",
                placeholder="e.g. Private helpers don't need docstrings.",
            )
        st.session_state.feedback[i] = (choice, reason)

    if result.comments and st.button("Submit Feedback"):
        acted = 0
        for i, c in enumerate(result.comments):
            choice, reason = st.session_state.feedback.get(i, ("No action", ""))
            if choice == "No action":
                continue
            if choice == "Accept":
                text = f"Flagged {c.title}; accepted."
            else:
                text = f"Rejected suggestion to {c.title}; reason: {reason or 'no reason given'}"
            try:
                memory.retain(project, text)
                acted += 1
            except memory.MemoryUnavailable as exc:
                st.warning(f"Hindsight unavailable, outcome not saved: {exc}")
                break
        if acted:
            st.success(f"Saved {acted} outcome(s) to team memory.")
