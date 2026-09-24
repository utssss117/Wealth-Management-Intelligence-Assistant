import streamlit as st
import requests

st.set_page_config(
    page_title="Wealth Management Intelligence Assistant",
    page_icon="💹",
    layout="centered",
)

BACKEND_URL = "http://localhost:8000/chat"

EXAMPLE_QUESTIONS = [
    "What is the NAV of HDFC Flexi Cap Fund?",
    "Compare HDFC Flexi Cap and HDFC Mid Cap Fund, and explain NAV",
    "What is an expense ratio?",
    "What is ELSS and what are its tax benefits?",
    "How does SEBI regulate mutual funds in India?",
]

if "messages" not in st.session_state:
    st.session_state.messages = []
if "prefill" not in st.session_state:
    st.session_state.prefill = ""

st.title("💹 Wealth Management Intelligence Assistant")

st.info(
    "⚠️ **Educational use only.** This assistant provides information about "
    "Indian mutual funds for learning purposes. It does **not** provide "
    "personalised investment advice. Consult a SEBI-registered advisor "
    "before making any investment decisions.",
    icon="ℹ️",
)
st.divider()

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
    st.caption("Backend: http://localhost:8000")
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

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
                resp = requests.post(
                    BACKEND_URL,
                    json={"question": user_input},
                    timeout=120,
                )
                resp.raise_for_status()
                answer = resp.json().get("answer", "No answer returned.")
            except requests.exceptions.ConnectionError:
                answer = (
                    "❌ **Could not reach the backend.**\n\n"
                    "Make sure the FastAPI server is running first:\n\n"
                    "    python -m uvicorn api.main:app --reload --port 8000"
                )
            except requests.exceptions.Timeout:
                answer = "⏱️ **Request timed out.** Try again in a moment."
            except requests.exceptions.HTTPError as e:
                answer = f"⚠️ **Backend error ({e.response.status_code}).** Please try again."
            except Exception as e:
                answer = f"⚠️ **Unexpected error:** {e}"
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
