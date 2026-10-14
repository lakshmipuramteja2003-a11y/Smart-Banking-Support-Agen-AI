# Smart Banking Support Agent

A single LangChain agent coordinates four tools: EMI calculation, loan eligibility, masked account lookup, and loan application submission. The Streamlit UI uses OpenRouter for chat, accepts customer follow-up answers, and requires an explicit confirmation button before submission.

## Run locally

From this directory, install dependencies, configure the OpenRouter settings, and start Streamlit:

```bash
python -m pip install -r requirements.txt
mkdir -p .streamlit
```

Create `.streamlit/secrets.toml` with your OpenRouter key and a model ID that supports tool calling. Choose a currently available free model if you want to use OpenRouter's free options:

```toml
OPENROUTER_API_KEY = "your-openrouter-api-key"
OPENROUTER_MODEL = "provider/model-name:free"
```

Then run:

```bash
streamlit run app.py
```

The example request is available in the sidebar. The agent asks for a customer ID before account lookup; the demo directory accepts `CUST1001` or `CUST1002`.

## Deploy to Streamlit Community Cloud

Deploy this folder's `app.py` as the app entry point. In the app's Streamlit Cloud settings, add these values under **Secrets**:

```toml
OPENROUTER_API_KEY = "your-openrouter-api-key"
OPENROUTER_MODEL = "provider/model-name:free"
```

Do not commit `.streamlit/secrets.toml`. Free model availability, rate limits, and tool-calling support depend on OpenRouter's current catalog and provider limits.

## Demo policy and safety

This is a local prototype, not a connection to a real bank. Account records and application submission are in-memory demo data. The EMI estimate uses a fixed 10.5% annual interest rate. Eligibility requires a monthly salary of at least ₹25,000, a 12-60 month term, and total monthly EMIs no greater than 50% of salary. These rules are illustrative and are not lending advice or a bank decision.

The application tool has a host-side confirmation gate: it remains blocked until the CLI receives the exact response `YES`. Submission also requires a successful eligibility result and matching verified account and loan terms. Do not use real customer data or credentials with this prototype.

Run the offline business-rule and confirmation tests with:

```bash
python -m unittest -v
```