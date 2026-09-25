import os
import sys
from pathlib import Path

# ── Ensure project root is on the path ──────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

# ── Secrets: Streamlit Cloud uses st.secrets; local dev falls back to .env ──
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
else:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

from agent.agent import ask_agent  # noqa: E402  (must come after env is set)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Wealth Management Intelligence Assistant",
    page_icon="💹",
    layout="centered",
)

EXAMPLE_QUESTIONS = [
    "What is the NAV of HDFC Flexi Cap Fund?",
    "Compare HDFC Flexi Cap and HDFC Mid Cap Fund, and explain NAV",
    "What is an expense ratio?",
    "What is ELSS and what are its tax benefits?",
    "How does SEBI regulate mutual funds in India?",
]

# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "prefill" not in st.session_state:
    st.session_state.prefill = ""

# ── Header ────────────────────────────────────────────────────────────────────
st.title("💹 Wealth Management Intelligence Assistant")

st.info(
    "⚠️ **Educational use only.** This assistant provides information about "
    "Indian mutual funds for learning purposes. It does **not** provide "
    "personalised investment advice. Consult a SEBI-registered advisor "
    "before making any investment decisions.",
    icon="ℹ️",
)
st.divider()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("💹 What can I help with?")
    st.markdown(
        "- 📊 **NAV lookup** — current price of any mutual fund\n"
        "- ⚖️ **Fund comparison** — compare NAVs across multiple funds\n"
        "- 📈 **NAV trend** — historical performance for a fund\n"
        "- 📚 **Concepts** — expense ratio, SIP, ELSS, SEBI regulations"
    )
    st.divider()
    st.subheader("🚀 Try an example")
    for q in EXAMPLE_QUESTIONS:
        if st.button(q, use_container_width=True, key="btn_" + q[:30]):
            st.session_state.prefill = q
            st.rerun()
    st.divider()
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ── Chat history ──────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Input handling ────────────────────────────────────────────────────────────
prefill_value = st.session_state.prefill
st.session_state.prefill = ""

user_input = (
    st.chat_input(placeholder="Ask about a fund NAV, concept, or comparison...")
    or prefill_value
)

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                answer = ask_agent(user_input, verbose=False)
            except EnvironmentError as e:
                answer = (
                    f"❌ **Configuration error:** {e}\n\n"
                    "Make sure `GROQ_API_KEY` is set in your Streamlit secrets."
                )
            except Exception as e:
                answer = f"⚠️ **Unexpected error:** {e}"
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})

