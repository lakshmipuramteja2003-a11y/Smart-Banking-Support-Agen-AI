# Smart Banking Support Agent

A single LangChain agent coordinates four tools: EMI calculation, loan eligibility, masked account lookup, and loan application submission. The CLI accepts customer follow-up answers, asks for an exact `YES` before submission, and prints a consolidated final summary.

## Run

From this directory, install the dependencies and configure an OpenAI API key:

```bash
python -m pip install -r requirements.txt
export OPENAI_API_KEY="your-api-key"
python banking_agent.py
```

The default model is `gpt-4o-mini`; override it with `OPENAI_MODEL` if needed. For the example request, the agent must ask for a customer ID before account lookup. The demo directory accepts `CUST1001` or `CUST1002`.

## Demo policy and safety

This is a local prototype, not a connection to a real bank. Account records and application submission are in-memory demo data. The EMI estimate uses a fixed 10.5% annual interest rate. Eligibility requires a monthly salary of at least ₹25,000, a 12-60 month term, and total monthly EMIs no greater than 50% of salary. These rules are illustrative and are not lending advice or a bank decision.

The application tool has a host-side confirmation gate: it remains blocked until the CLI receives the exact response `YES`. Submission also requires a successful eligibility result and matching verified account and loan terms. Do not use real customer data or credentials with this prototype.

Run the offline business-rule and confirmation tests with:

```bash
python -m unittest -v
```