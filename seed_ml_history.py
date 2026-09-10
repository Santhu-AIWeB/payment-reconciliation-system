import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "http://localhost:8000"

# This script only ADDS simulated historical transactions.
# It does not delete or modify your existing transactions.
#
# It creates enough history for the AI service to use IsolationForest
# instead of the rule-based fallback.
#
# Existing database:
#   4 current transactions
# After this script:
#   16+ transactions
#
# The script is safe to run again: if the database already has 10+
# transactions, it stops without creating more history.

NORMAL_CASES = [
    (700, "SUCCESS", "DEBITED"),
    (850, "SUCCESS", "DEBITED"),
    (1200, "SUCCESS", "DEBITED"),
    (1450, "SUCCESS", "DEBITED"),
    (1800, "SUCCESS", "DEBITED"),
    (2200, "SUCCESS", "DEBITED"),
    (2600, "SUCCESS", "DEBITED"),
    (3200, "SUCCESS", "DEBITED"),
]

ANOMALY_CASES = [
    (4100, "FAILED", "DEBITED"),
    (4700, "TIMEOUT", "DEBITED"),
    (5300, "SUCCESS", "NOT_DEBITED"),
    (6100, "TIMEOUT", "NOT_DEBITED"),
]

def api_request(method, path, payload=None):
    url = f"{BASE_URL}{path}"
    data = None

    headers = {
        "Accept": "application/json",
    }

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=data, headers=headers, method=method)

    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc

def check_backend():
    try:
        return api_request("GET", "/api/dashboard/summary")
    except RuntimeError as exc:
        print("ERROR: Backend is not reachable.")
        print("Make sure Docker is running with:")
        print("  docker compose up -d")
        print()
        print(f"Details: {exc}")
        sys.exit(1)

def get_transactions():
    try:
        return api_request("GET", "/api/transactions")
    except RuntimeError as exc:
        print(f"ERROR: Could not read transactions: {exc}")
        sys.exit(1)

def create_transaction(amount):
    try:
        data = api_request(
            "POST",
            "/api/transactions",
            {
                "amount": amount,
                "currency": "INR",
            },
        )
        return data["transaction_id"]
    except RuntimeError as exc:
        raise RuntimeError(f"Transaction creation failed: {exc}") from exc

def process_gateway(transaction_id, outcome):
    api_request(
        "POST",
        "/api/gateway/process",
        {
            "transaction_id": transaction_id,
            "outcome": outcome,
        },
    )

def process_bank(transaction_id, outcome):
    api_request(
        "POST",
        "/api/bank/process",
        {
            "transaction_id": transaction_id,
            "outcome": outcome,
        },
    )

def reconcile(transaction_id):
    return api_request(
        "POST",
        "/api/reconciliation/process",
        {
            "transaction_id": transaction_id,
        },
    )

def main():
    print("=" * 60)
    print("Payment Reconciliation - ML History Seeder")
    print("=" * 60)
    print()

    check_backend()

    existing = get_transactions()
    print(f"Existing transactions: {len(existing)}")

    if len(existing) >= 10:
        print()
        print("Database already has 10+ transactions.")
        print("No seed data was added.")
        print("AI should already be able to use IsolationForest.")
        return

    cases = NORMAL_CASES + ANOMALY_CASES
    print(f"Adding {len(cases)} simulated historical cases...")
    print()

    created = []

    for index, (amount, gateway_outcome, bank_outcome) in enumerate(cases, start=1):
        try:
            transaction_id = create_transaction(amount)

            process_gateway(transaction_id, gateway_outcome)
            process_bank(transaction_id, bank_outcome)
            reconciliation = reconcile(transaction_id)

            created.append(transaction_id)

            print(
                f"[{index:02d}/{len(cases)}] "
                f"{transaction_id} | "
                f"₹{amount} | "
                f"Gateway={gateway_outcome} | "
                f"Bank={bank_outcome} | "
                f"Recon={reconciliation.get('reconciliation_status')} | "
                f"Action={reconciliation.get('action_required')}"
            )

        except RuntimeError as exc:
            print()
            print(f"ERROR while processing case {index}.")
            print(exc)
            print()
            print("The transactions created before this error were not deleted.")
            sys.exit(1)

    print()
    print("=" * 60)
    print("SEEDING COMPLETE")
    print("=" * 60)

    final_transactions = get_transactions()
    print(f"Transactions now in database: {len(final_transactions)}")
    print(f"Historical cases added: {len(created)}")
    print()
    print("Expected AI behavior:")
    print("  Training samples: 10+")
    print("  Model: isolation_forest")
    print()
    print("Open:")
    print("  http://localhost:5173")
    print()
    print("Then:")
    print("  Investigations -> Analyze")
    print()
    print("Note: this is simulation data only. No real bank, card, UPI,")
    print("or payment money movement is involved.")

if __name__ == "__main__":
    main()
