"""
app.py — the interface.

Run it from a terminal in this folder:

    streamlit run app.py

Note there is no agent logic in this file at all. It calls into agent.py. That
separation is what makes it possible to change the front end without touching
anything that decides what the agent does.
"""

from __future__ import annotations

import uuid

import streamlit as st
from langgraph.types import Command

import agent as agent_module

st.set_page_config(page_title="Nile Systems HR Agent", page_icon="💬",
                   layout="centered")

PURPLE = "#574C99"


# ---------------------------------------------------------------- resources

@st.cache_resource(show_spinner="Starting the agent…")
def get_agent():
    """Built once and reused. The checkpointer lives in here, which is what
    keeps memory alive between Streamlit reruns."""
    return agent_module.build_agent()


def thread_config():
    return {"configurable": {"thread_id": st.session_state.thread_id}}


# ---------------------------------------------------------------- state

if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"user-{uuid.uuid4().hex[:8]}"
if "history" not in st.session_state:
    st.session_state.history = []
if "pending" not in st.session_state:
    st.session_state.pending = None      # an approval waiting for a human


# ---------------------------------------------------------------- sidebar

with st.sidebar:
    st.markdown(f"### <span style='color:{PURPLE}'>Nile Systems HR Agent</span>",
                unsafe_allow_html=True)
    st.caption("Arabian Academy · Session 5")

    if not agent_module.has_api_key():
        st.error("No GROQ_API_KEY found.\n\nCopy `.env.example` to `.env`, paste "
                 "your key, and restart the app.")
        st.stop()

    st.success("API key loaded")

    backend = agent_module.retrieval_backend()
    if backend == "semantic":
        st.info("Search: **semantic** (embeddings)")
    else:
        st.warning("Search: **keyword** fallback\n\nsentence-transformers is not "
                   "installed. The app works, but it matches words rather than "
                   "meaning.")

    st.divider()
    st.markdown("**Conversation**")
    st.code(st.session_state.thread_id, language=None)
    st.caption("Everything the agent remembers is tied to this ID. "
               "A different ID is a different person.")

    if st.button("Start a new conversation", use_container_width=True):
        st.session_state.thread_id = f"user-{uuid.uuid4().hex[:8]}"
        st.session_state.history = []
        st.session_state.pending = None
        st.rerun()

    st.divider()
    st.markdown("**Tools available**")
    for t in agent_module.READ_TOOLS:
        st.markdown(f"- `{t.name}` · read")
    for t in agent_module.WRITE_TOOLS:
        st.markdown(f"- `{t.name}` · **write, gated**")


# ---------------------------------------------------------------- tabs

chat_tab, about_tab = st.tabs(["Chat", "Handover"])

# The chat box. Placing it here at the top level of the page — not inside the
# tab — is what makes Streamlit pin it to the bottom of the window. Inside a tab
# it renders inline, just under the heading. It is disabled while an approval is
# pending, so a booking cannot be interrupted by a new question.
prompt = st.chat_input(
    "e.g. How many leave days do I get?",
    disabled=st.session_state.pending is not None,
)


# ============================================================ CHAT
with chat_tab:
    st.markdown("#### Ask about leave, expenses or public holidays")

    for role, content in st.session_state.history:
        with st.chat_message(role):
            st.markdown(content)

    # --- an approval is waiting: block further chat until it is answered
    if st.session_state.pending:
        req = st.session_state.pending
        with st.chat_message("assistant"):
            st.warning("**Approval required before this can go ahead**")
            st.json(req)
            st.caption("The agent has paused. Nothing has been written yet — and "
                       "nothing will be until a person decides.")
            c1, c2 = st.columns(2)
            approve = c1.button("Approve", type="primary", use_container_width=True)
            decline = c2.button("Decline", use_container_width=True)

        if approve or decline:
            decision = "approve" if approve else "decline"
            with st.spinner("Resuming…"):
                result = get_agent().invoke(Command(resume=decision),
                                            thread_config())
            st.session_state.pending = None
            answer = result["messages"][-1].content or "(no answer returned)"
            st.session_state.history.append(("assistant", answer))
            st.rerun()

    elif prompt:
        st.session_state.history.append(("user", prompt))
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                try:
                    result = get_agent().invoke(
                        {"messages": [("user", prompt)]}, thread_config()
                    )
                except Exception as exc:
                    st.error(f"{type(exc).__name__}: {exc}")
                    st.stop()

            if "__interrupt__" in result:
                st.session_state.pending = result["__interrupt__"][0].value
                st.rerun()

            answer = result["messages"][-1].content or "(no answer returned)"
            st.markdown(answer)

            calls = []
            for m in result["messages"]:
                for c in getattr(m, "tool_calls", None) or []:
                    calls.append(f"`{c['name']}` {c['args']}")
            if calls:
                with st.expander(f"Tools called ({len(calls)})"):
                    for c in calls:
                        st.markdown(f"- {c}")

        st.session_state.history.append(("assistant", answer))


# ============================================================ HANDOVER
with about_tab:
    st.markdown("#### Handover note")
    st.caption("What a sponsor needs to read before saying yes.")

    st.markdown(
        """
**What it does**
Answers staff questions about annual leave, carry over, booking rules, travel
expenses and refund approval limits, using the Nile Systems handbook. It can also
look up public holidays, and request a leave booking.

**Where its answers come from**
- The handbook, via retrieval — not from the model's own knowledge
- The public holiday API, for dates
- The conversation itself, for what the user has already said

**What it must never do**
- State a figure that did not come from a tool
- Book leave without a named person approving it first
- Answer a policy question the handbook does not cover

**Known limitations**
- Public holiday dates for Eid are estimates. They depend on moon sightings and
  cannot be calculated reliably in advance.
- Memory is held in RAM. Restart the app and every conversation is gone.
- Approval is a single approver. There is no second signature for large amounts.

**Before this goes anywhere near real staff**
1. Swap the in-memory checkpointer for a database-backed one
2. Add authentication, so `thread_id` maps to a real person
3. Decide who receives the escalation when the agent refuses
"""
    )

    st.divider()
    st.markdown("**Risk register**")
    st.dataframe(
        {
            "Risk": [
                "Answers from a stale handbook version",
                "Wrong person sees another's conversation",
                "Approver clicks Approve without reading",
                "Holiday date is wrong for a religious holiday",
            ],
            "Likelihood": ["Medium", "Low", "High", "Medium"],
            "Impact": ["Medium", "High", "High", "Low"],
            "Mitigation": [
                "Review key answers whenever the handbook changes",
                "Authentication before launch; thread_id is not identity",
                "Show the full request in the approval box, as this app does",
                "Flag Islamic holidays as estimated in the answer",
            ],
        },
        use_container_width=True, hide_index=True,
    )
