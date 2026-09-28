"""Streamlit UI: memory-powered code reviews that learn team standards."""

from __future__ import annotations

from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

import streamlit as st

import memory
import reviewer

st.set_page_config(page_title="Hindsight Code Review", layout="wide")

# Badge tints are translucent and the text inherits the active theme colour, so
# the same badges read correctly in both the light and dark themes.
SEVERITY_COLORS = {
    "Critical": ("rgba(220, 53, 69, 0.18)", "rgba(220, 53, 69, 0.55)"),
    "Major": ("rgba(245, 158, 11, 0.20)", "rgba(245, 158, 11, 0.55)"),
    "Minor": ("rgba(100, 116, 139, 0.22)", "rgba(100, 116, 139, 0.55)"),
    "Suggestion": ("rgba(100, 116, 139, 0.22)", "rgba(100, 116, 139, 0.55)"),
}
DEFAULT_BADGE = SEVERITY_COLORS["Suggestion"]

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
if "accepted" not in st.session_state:
    st.session_state.accepted = 0
if "rejected" not in st.session_state:
    st.session_state.rejected = 0
if "review_seq" not in st.session_state:
    st.session_state.review_seq = 0
if "feedback_saved_for" not in st.session_state:
    st.session_state.feedback_saved_for = -1
if "fixed" not in st.session_state:
    st.session_state.fixed = None

# --- header -------------------------------------------------------------------
st.title("Hindsight Code Review")
st.caption("Memory-powered reviews that learn your team's standards.")
project = st.selectbox("Project", list(memory.PROJECTS), index=0)

# --- sidebar ------------------------------------------------------------------
with st.sidebar:
    st.subheader("Team memory")
    st.caption(
        f"Accepted {st.session_state.accepted} · "
        f"Rejected {st.session_state.rejected}"
    )
    if st.button("View team memory", use_container_width=True):
        try:
            mems = memory.recall(
                project, "team coding conventions, standards and preferences"
            )
        except memory.MemoryUnavailable as exc:
            st.warning(f"Hindsight unavailable: {exc}")
            mems = []
        with st.expander(f"{len(mems)} memories match", expanded=True):
            for m in mems:
                st.write(f"- {m}")

    st.subheader("Review history")
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
    st.session_state.fixed = None
    st.session_state.review_seq += 1
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
            # Rerun so the sidebar (history, tally) reflects this review
            # in the same interaction instead of lagging one run behind.
            st.rerun()
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
        bg, border = SEVERITY_COLORS.get(c.severity, DEFAULT_BADGE)
        st.markdown(
            f"<span style='background:{bg};border:1px solid {border};color:inherit;"
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

    saved = st.session_state.feedback_saved_for == st.session_state.review_seq
    if saved:
        st.caption("Feedback saved for this review.")
    if result.comments and st.button("Submit Feedback", disabled=saved):
        acted = 0
        with st.spinner("Saving feedback to team memory..."):
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
                    if choice == "Accept":
                        st.session_state.accepted += 1
                    else:
                        st.session_state.rejected += 1
                except memory.MemoryUnavailable as exc:
                    st.warning(f"Hindsight unavailable, outcome not saved: {exc}")
                    break
        if acted:
            st.success(f"Saved {acted} outcome(s) to team memory.")
            st.session_state.feedback_saved_for = st.session_state.review_seq
            # Rerun so the Submit button disables immediately instead of
            # staying clickable until the next interaction.
            st.rerun()

    if result.comments:
        st.subheader("Fixed code")
        applyable = [
            c
            for i, c in enumerate(result.comments)
            if st.session_state.feedback.get(i, ("No action", ""))[0] != "Reject"
        ]
        if not applyable:
            st.caption("All findings rejected — nothing to apply.")
        elif st.button("Generate fixed code"):
            with st.spinner("Applying accepted findings..."):
                try:
                    st.session_state.fixed = reviewer.apply_fixes(
                        st.session_state.code, applyable
                    )
                except (reviewer.ReviewError, ValueError) as exc:
                    st.error(str(exc))
                    st.session_state.fixed = None
        fixed = st.session_state.fixed
        if fixed is not None:
            st.code(fixed.fixed_code, language="python")
            st.download_button(
                "Download fixed code",
                fixed.fixed_code,
                file_name="fixed_code.py",
            )
            st.caption(
                f"Applied {len(fixed.applied)} finding(s)"
                + (f" with `{fixed.model_used}`" if fixed.model_used else "")
                + f" · {fixed.prompt_tokens} input / "
                f"{fixed.completion_tokens} output tokens"
            )
