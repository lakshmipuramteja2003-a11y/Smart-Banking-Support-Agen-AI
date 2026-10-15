"""Demo single-agent banking support workflow with guarded loan submission."""

from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass
from typing import Any


ANNUAL_INTEREST_RATE = 10.5
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEMO_ACCOUNTS = {
    "CUST1001": {
        "customer_name": "Aarav Sharma",
        "account_number": "XXXXXX4821",
        "account_type": "Savings",
        "branch": "Mumbai Central",
    },
    "CUST1002": {
        "customer_name": "Diya Patel",
        "account_number": "XXXXXX7306",
        "account_type": "Savings",
        "branch": "Bengaluru South",
    },
}


def resolve_ai_settings() -> tuple[str | None, str, str | None]:
    """Return the active API credentials and model for the demo app.

    Prefer OpenRouter environment keys because the app docs and Streamlit UI use
    OpenRouter, while preserving compatibility with the older OpenAI environment
    names used by the CLI example.
    """
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    model_name = os.getenv("OPENROUTER_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    base_url = os.getenv("OPENROUTER_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    if api_key and base_url is None:
        base_url = OPENROUTER_BASE_URL
    elif not api_key:
        base_url = None
    return api_key, model_name, base_url


def calculate_monthly_emi(
    principal: float,
    annual_interest_rate: float,
    tenure_months: int,
) -> float:
    """Calculate a fixed-rate monthly EMI, rounded to paise."""
    if principal <= 0:
        raise ValueError("Loan amount must be greater than zero.")
    if annual_interest_rate < 0:
        raise ValueError("Interest rate cannot be negative.")
    if tenure_months <= 0:
        raise ValueError("Tenure must be at least one month.")

    monthly_rate = annual_interest_rate / 100 / 12
    if monthly_rate == 0:
        return round(principal / tenure_months, 2)

    growth = (1 + monthly_rate) ** tenure_months
    emi = principal * monthly_rate * growth / (growth - 1)
    return round(emi, 2)


@dataclass
class BankingSession:
    """In-memory demo banking state shared by tools and the host UI."""

    last_eligibility: dict[str, Any] | None = None
    account_details: dict[str, str] | None = None
    application: dict[str, Any] | None = None
    confirmation_authorized: bool = False

    def check_loan_eligibility(
        self,
        monthly_salary: float,
        existing_emi: float,
        loan_amount: float,
        tenure_months: int,
    ) -> dict[str, Any]:
        if monthly_salary <= 0:
            raise ValueError("Monthly salary must be greater than zero.")
        if existing_emi < 0:
            raise ValueError("Existing EMI cannot be negative.")

        proposed_emi = calculate_monthly_emi(
            loan_amount, ANNUAL_INTEREST_RATE, tenure_months
        )
        total_monthly_debt = existing_emi + proposed_emi
        debt_to_income = total_monthly_debt / monthly_salary
        reasons = []
        if monthly_salary < 25_000:
            reasons.append("Monthly salary is below the demo minimum of ₹25,000.")
        if not 12 <= tenure_months <= 60:
            reasons.append("The demo supports loan terms from 12 to 60 months.")
        if debt_to_income > 0.5:
            reasons.append("Total monthly EMIs exceed 50% of monthly salary.")

        self.last_eligibility = {
            "eligible": not reasons,
            "loan_amount": loan_amount,
            "tenure_months": tenure_months,
            "monthly_emi": proposed_emi,
            "existing_emi": existing_emi,
            "total_monthly_debt": round(total_monthly_debt, 2),
            "debt_to_income_percent": round(debt_to_income * 100, 2),
            "annual_interest_rate": ANNUAL_INTEREST_RATE,
            "reasons": reasons,
        }
        return self.last_eligibility

    def get_account_details(self, customer_id: str) -> dict[str, str]:
        normalized_id = customer_id.strip().upper()
        if not normalized_id:
            raise ValueError("A customer ID is required to look up an account.")
        details = DEMO_ACCOUNTS.get(normalized_id)
        if details is None:
            raise ValueError("Customer ID was not found in the demo directory.")

        self.account_details = {"customer_id": normalized_id, **details}
        return self.account_details

    def submit_loan_application(
        self,
        customer_id: str,
        loan_amount: float,
        tenure_months: int,
    ) -> dict[str, Any]:
        if not self.confirmation_authorized:
            return {"submitted": False, "message": "Blocked: customer confirmation is required."}
        if self.application is not None:
            return {"submitted": False, "message": "An application was already submitted in this session."}
        if self.account_details is None or self.account_details["customer_id"] != customer_id.strip().upper():
            return {"submitted": False, "message": "Retrieve and verify the customer's account before applying."}
        if self.last_eligibility is None or not self.last_eligibility["eligible"]:
            return {"submitted": False, "message": "A successful eligibility check is required before applying."}
        if (
            self.last_eligibility["loan_amount"] != loan_amount
            or self.last_eligibility["tenure_months"] != tenure_months
        ):
            return {"submitted": False, "message": "Application terms do not match the eligible loan terms."}

        self.application = {
            "submitted": True,
            "application_id": f"DEMO-{uuid.uuid4().hex[:8].upper()}",
            "customer_id": self.account_details["customer_id"],
            "loan_amount": loan_amount,
            "tenure_months": tenure_months,
            "status": "Submitted (demo only)",
        }
        self.confirmation_authorized = False
        return self.application

    def authorize_submission(self) -> None:
        """Grant one submission attempt after host-side customer confirmation."""
        self.confirmation_authorized = True


def create_banking_agent(
    session: BankingSession,
    model_name: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Any:
    """Create the LangChain agent and bind its tools to this session."""
    from langchain.agents import create_agent
    from langchain.tools import tool
    from langchain_openai import ChatOpenAI

    @tool
    def calculate_emi(loan_amount: float, tenure_months: int) -> dict[str, Any]:
        """Calculate the monthly EMI using the demo annual rate of 10.5%."""
        emi = calculate_monthly_emi(
            loan_amount, ANNUAL_INTEREST_RATE, tenure_months
        )
        return {
            "monthly_emi": emi,
            "annual_interest_rate": ANNUAL_INTEREST_RATE,
            "currency": "INR",
        }

    @tool
    def check_loan_eligibility(
        monthly_salary: float,
        existing_emi: float,
        loan_amount: float,
        tenure_months: int,
    ) -> dict[str, Any]:
        """Check demo eligibility: salary at least ₹25,000, term 12-60 months, and total EMIs no more than 50% of salary."""
        return session.check_loan_eligibility(
            monthly_salary, existing_emi, loan_amount, tenure_months
        )

    @tool
    def get_account_details(customer_id: str) -> dict[str, str]:
        """Retrieve masked account details using a demo customer ID."""
        return session.get_account_details(customer_id)

    @tool
    def submit_loan_application(
        customer_id: str,
        loan_amount: float,
        tenure_months: int,
    ) -> dict[str, Any]:
        """Submit the eligible application only after host-verified customer confirmation."""
        return session.submit_loan_application(
            customer_id, loan_amount, tenure_months
        )

    model = ChatOpenAI(
        model=model_name,
        temperature=0,
        api_key=api_key,
        base_url=base_url,
    )
    return create_agent(
        model=model,
        tools=[
            calculate_emi,
            check_loan_eligibility,
            get_account_details,
            submit_loan_application,
        ],
        system_prompt=(
            "You are a careful banking support agent operating a demo system. "
            "Use tools for calculations, eligibility, account lookup, and submission. "
            "Ask the customer for missing information instead of guessing, especially "
            "their customer ID. Do not claim an account lookup or application succeeded "
            "unless its tool succeeds. The host will ask for explicit confirmation "
            "before permitting submission; if submission is blocked, do not retry or "
            "claim it was filed. Explain the demo eligibility policy and the 10.5% "
            "annual interest assumption when reporting results."
        ),
    )


def _format_final_summary(session: BankingSession, declined: bool = False) -> str:
    lines = ["\nFinal summary"]
    eligibility = session.last_eligibility
    if eligibility is None:
        lines.append("EMI: Not calculated")
        lines.append("Eligibility: Not checked")
    else:
        lines.append(
            f"EMI: ₹{eligibility['monthly_emi']:,.2f}/month at "
            f"{eligibility['annual_interest_rate']}% annual interest"
        )
        result = "Eligible" if eligibility["eligible"] else "Not eligible"
        lines.append(f"Eligibility: {result}")
        if eligibility["reasons"]:
            lines.append("Reason: " + " ".join(eligibility["reasons"]))

    if session.account_details:
        account = session.account_details
        lines.append(
            f"Account: {account['account_type']} {account['account_number']} "
            f"for {account['customer_name']} ({account['branch']})"
        )
    else:
        lines.append("Account: Not retrieved")

    if session.application:
        lines.append(
            f"Application: {session.application['status']} "
            f"({session.application['application_id']})"
        )
    elif declined:
        lines.append("Application: Not submitted; confirmation was declined.")
    else:
        lines.append("Application: Not submitted")
    return "\n".join(lines)


def main() -> int:
    api_key, model_name, base_url = resolve_ai_settings()
    if not api_key:
        print(
            "Set OPENROUTER_API_KEY (or OPENAI_API_KEY) before starting the "
            "LangChain agent."
        )
        return 1

    session = BankingSession()
    try:
        agent = create_banking_agent(
            session,
            model_name,
            api_key=api_key,
            base_url=base_url,
        )
    except ImportError as error:
        print(f"Missing agent dependency: {error}. Install this folder's requirements.txt.")
        return 1

    default_request = (
        "I want to apply for a personal loan of ₹5,00,000 for three years. "
        "My monthly salary is ₹60,000, and I already pay ₹5,000 as an EMI for "
        "another loan. Calculate my monthly EMI, check my loan eligibility, "
        "retrieve my account details, and help me submit a loan application if I qualify."
    )
    customer_message = input("Customer request (press Enter for the example): ").strip()
    if not customer_message:
        customer_message = default_request

    conversation: list[Any] = []
    confirmation_attempted = False
    while True:
        result = agent.invoke(
            {"messages": [*conversation, {"role": "user", "content": customer_message}]}
        )
        conversation = result["messages"]
        assistant_message = conversation[-1]
        response_text = getattr(assistant_message, "content", str(assistant_message))
        if isinstance(response_text, list):
            response_text = " ".join(
                part.get("text", "") for part in response_text if isinstance(part, dict)
            )
        print(f"\nAgent: {response_text}")

        if session.application is not None:
            print(_format_final_summary(session))
            break
        if session.last_eligibility is not None and not session.last_eligibility["eligible"]:
            print(_format_final_summary(session))
            break
        if confirmation_attempted:
            print(_format_final_summary(session))
            break
        if (
            session.last_eligibility is not None
            and session.last_eligibility["eligible"]
            and session.account_details is not None
        ):
            eligibility = session.last_eligibility
            confirmation = input(
                "Submit the ₹{:,.2f} loan for {} months to account {}? Type YES to confirm: ".format(
                    eligibility["loan_amount"],
                    eligibility["tenure_months"],
                    session.account_details["account_number"],
                )
            ).strip()
            if confirmation != "YES":
                print(_format_final_summary(session, declined=True))
                break
            session.authorize_submission()
            confirmation_attempted = True
            customer_message = (
                "The customer has explicitly confirmed the exact loan terms just "
                "shown. Submit the application now using the verified account and "
                "eligibility details."
            )
            continue

        customer_message = input("\nYou (provide the requested missing information): ").strip()
        if not customer_message:
            print(_format_final_summary(session))
            break

    return 0


if __name__ == "__main__":
    sys.exit(main())