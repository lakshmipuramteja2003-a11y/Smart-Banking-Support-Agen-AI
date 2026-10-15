"""Streamlit chat interface for the OpenRouter-backed banking demo agent."""

from __future__ import annotations

import os
from typing import Any

import streamlit as st

from banking_agent import BankingSession, _format_final_summary, create_banking_agent


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
EXAMPLE_REQUEST = (
    "I want to apply for a personal loan of ₹5,00,000 for three years. "
    "My monthly salary is ₹60,000, and I already pay ₹5,000 as an EMI for "
    "another loan. Calculate my monthly EMI, check my loan eligibility, "
    "retrieve my account details, and help me submit a loan application if I qualify."
)


def _setting(name: str) -> str:
    environment_value = os.getenv(name, "")
    if environment_value:
        return environment_value
    try:
        return str(st.secrets.get(name, ""))
    except Exception:
        return ""


def _assistant_text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict)
        )
    return str(content)


def _invoke_agent(prompt: str) -> str:
    result = st.session_state.agent.invoke(
        {
            "messages": [
                *st.session_state.agent_messages,
                {"role": "user", "content": prompt},
            ]
        }
    )
    st.session_state.agent_messages = result["messages"]
    return _assistant_text(st.session_state.agent_messages[-1])


def _append_agent_turn(prompt: str) -> None:
    try:
        response = _invoke_agent(prompt)
    except Exception as error:
        details = str(error).replace(api_key, "[redacted]") if api_key else str(error)
        response = f"Request failed ({type(error).__name__}): {details}"
    st.session_state.chat_history.append({"role": "assistant", "content": response})


st.set_page_config(page_title="Banking Support Agent", page_icon="🏦")

if "banking_session" not in st.session_state:
    st.session_state.banking_session = BankingSession()
    st.session_state.agent_messages = []
    st.session_state.chat_history = []
    st.session_state.agent = None
    st.session_state.active_model = ""
    st.session_state.confirmation_attempted = False
    st.session_state.confirmation_declined = False

if "model_id_input" not in st.session_state:
    st.session_state.model_id_input = _setting("OPENROUTER_MODEL")

api_key = _setting("OPENROUTER_API_KEY")

with st.sidebar:
    st.title("Banking Support")
    st.caption("Demo loan support agent")
    model_name = st.text_input(
        "OpenRouter model ID",
        key="model_id_input",
        placeholder="provider/model-name:free",
    ).strip()
    st.caption("Choose an OpenRouter model that supports tool calling.")
    if st.button("Load example request", use_container_width=True):
        st.session_state.pending_prompt = EXAMPLE_REQUEST
        st.rerun()
    if st.button("New conversation", use_container_width=True):
        for key in (
            "banking_session",
            "agent_messages",
            "chat_history",
            "agent",
            "active_model",
            "confirmation_attempted",
            "confirmation_declined",
            "pending_prompt",
        ):
            st.session_state.pop(key, None)
        st.rerun()

if not api_key:
    st.info("Add OPENROUTER_API_KEY to Streamlit Secrets to enable the agent.")
if not model_name:
    st.info("Enter an OpenRouter model ID in the sidebar to continue.")

if api_key and model_name:
    if st.session_state.agent is None or st.session_state.active_model != model_name:
        try:
            st.session_state.agent = create_banking_agent(
                st.session_state.banking_session,
                model_name,
                api_key=api_key,
                base_url=OPENROUTER_BASE_URL,
            )
            st.session_state.active_model = model_name
            st.session_state.agent_messages = []
        except ImportError:
            st.error("Install the packages listed in requirements.txt, then restart the app.")

st.title("Personal Loan Support")
st.caption("EMI estimate · demo eligibility · masked demo account lookup")

for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

pending_prompt = st.session_state.pop("pending_prompt", None)
prompt = pending_prompt or st.chat_input(
    "Ask about a personal loan",
    disabled=st.session_state.agent is None,
)
if prompt:
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    _append_agent_turn(prompt)
    st.rerun()

banking_session = st.session_state.banking_session
eligibility = banking_session.last_eligibility
confirmation_ready = (
    eligibility is not None
    and eligibility["eligible"]
    and banking_session.account_details is not None
    and banking_session.application is None
    and not st.session_state.confirmation_attempted
    and not st.session_state.confirmation_declined
)

if confirmation_ready:
    account = banking_session.account_details
    st.subheader("Review loan application")
    st.write(
        f"₹{eligibility['loan_amount']:,.2f} for {eligibility['tenure_months']} months "
        f"to {account['account_type']} account {account['account_number']}"
    )
    st.write(f"Estimated EMI: ₹{eligibility['monthly_emi']:,.2f}/month")
    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button("Confirm and submit", type="primary", use_container_width=True):
            banking_session.authorize_submission()
            st.session_state.confirmation_attempted = True
            st.session_state.chat_history.append(
                {"role": "user", "content": "Confirmed: submit this application."}
            )
            _append_agent_turn(
                "The customer confirmed the loan terms shown by the host. "
                "Submit the application now using the verified account and eligibility details."
            )
            st.rerun()
    with cancel_col:
        if st.button("Cancel", use_container_width=True):
            st.session_state.confirmation_declined = True
            st.rerun()

if banking_session.application is not None:
    st.success(_format_final_summary(banking_session))
elif st.session_state.confirmation_declined:
    st.info(_format_final_summary(banking_session, declined=True))
elif eligibility is not None and not eligibility["eligible"]:
    st.warning(_format_final_summary(banking_session))