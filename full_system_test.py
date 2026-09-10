import json
import urllib.request
import urllib.error

BASE = "http://localhost:8000"

CASES = [
    {"name": "FAILED + DEBITED", "amount": 7201, "gateway": "FAILED", "bank": "DEBITED", "expected_rec": "MISMATCH", "expected_action": "REFUND"},
    {"name": "SUCCESS + NOT_DEBITED", "amount": 7202, "gateway": "SUCCESS", "bank": "NOT_DEBITED", "expected_rec": "MISMATCH", "expected_action": "RETRY"},
    {"name": "TIMEOUT + DEBITED", "amount": 7203, "gateway": "TIMEOUT", "bank": "DEBITED", "expected_rec": "MISMATCH", "expected_action": "INVESTIGATE"},
    {"name": "TIMEOUT + NOT_DEBITED", "amount": 7204, "gateway": "TIMEOUT", "bank": "NOT_DEBITED", "expected_rec": "PENDING", "expected_action": "RETRY"},
    {"name": "SUCCESS + DELAYED", "amount": 7205, "gateway": "SUCCESS", "bank": "DELAYED", "expected_rec": "PENDING", "expected_action": "WAIT"},
]

def request(method, path, payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            body = json.loads(raw)
        except Exception:
            body = raw
        return e.code, body

def post(path, payload):
    return request("POST", path, payload)

def get(path):
    return request("GET", path)

def check(condition, message):
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {message}")
    return condition

print("=" * 72)
print("PAYMENT RECONCILIATION - FULL SYSTEM TEST")
print("=" * 72)

status, health = get("/api/dashboard/summary")
if not check(status == 200, f"Backend reachable: HTTP {status}"):
    raise SystemExit(1)

print("\nCreating and testing 5 fresh scenarios...\n")

results = []
all_passed = True

for case in CASES:
    print("-" * 72)
    print(case["name"])

    status, txn = post("/api/transactions", {
        "amount": case["amount"],
        "currency": "INR"
    })
    ok = check(status == 201 and "transaction_id" in txn, "Transaction created")
    all_passed &= ok
    if not ok:
        continue

    txn_id = txn["transaction_id"]
    print(f"  Transaction: {txn_id}")

    status, gateway = post("/api/gateway/process", {
        "transaction_id": txn_id,
        "outcome": case["gateway"]
    })
    all_passed &= check(
        status == 200 and gateway.get("status") == case["gateway"],
        f"Gateway = {case['gateway']}"
    )

    status, bank = post("/api/bank/process", {
        "transaction_id": txn_id,
        "outcome": case["bank"]
    })
    all_passed &= check(
        status == 200 and bank.get("status") == case["bank"],
        f"Bank = {case['bank']}"
    )

    status, rec = post("/api/reconciliation/process", {
        "transaction_id": txn_id
    })
    all_passed &= check(status == 200, "Reconciliation processed")
    all_passed &= check(
        rec.get("reconciliation_status") == case["expected_rec"],
        f"Reconciliation = {rec.get('reconciliation_status')} (expected {case['expected_rec']})"
    )
    all_passed &= check(
        rec.get("action_required") == case["expected_action"],
        f"Action = {rec.get('action_required')} (expected {case['expected_action']})"
    )

    # Verify AI is using the trained Isolation Forest.
    status, ai = get(f"/api/ai/analyze/{txn_id}")
    all_passed &= check(status == 200, "AI analysis endpoint works")
    all_passed &= check(
        ai.get("model_type") == "isolation_forest",
        f"AI model = {ai.get('model_type')}"
    )
    all_passed &= check(
        int(ai.get("training_samples", 0)) >= 10,
        f"AI training samples = {ai.get('training_samples')}"
    )

    # Exercise the automated action for eligible workflows.
    if case["expected_action"] == "REFUND":
        status, refund = post("/api/refunds/process", {"transaction_id": txn_id})
        all_passed &= check(
            status == 200 and refund.get("status") == "COMPLETED",
            f"Refund workflow = {refund.get('status')}"
        )

    elif case["expected_action"] == "RETRY":
        status, retry = post("/api/retry/process", {"transaction_id": txn_id})
        all_passed &= check(
            status == 200 and retry.get("status") == "SUCCESS",
            f"Retry workflow = {retry.get('status')}"
        )

    # Final enriched detail verification.
    status, detail = get(f"/api/dashboard/transactions/{txn_id}")
    all_passed &= check(status == 200, "Dashboard transaction detail loads")

    if case["expected_action"] == "REFUND":
        all_passed &= check(
            detail.get("refund", {}).get("status") == "COMPLETED",
            "Refund appears in transaction detail"
        )

    if case["expected_action"] == "RETRY":
        retries = detail.get("retries") or []
        all_passed &= check(
            any(item.get("status") == "SUCCESS" for item in retries),
            "Successful retry appears in transaction detail"
        )

    results.append(txn_id)

print("\n" + "=" * 72)
print("FINAL RESULT")
print("=" * 72)

status, summary = get("/api/dashboard/summary")
if status == 200:
    print(json.dumps(summary, indent=2))

print(f"\nTest transaction IDs: {', '.join(results)}")

if all_passed:
    print("\nRESULT: ALL TESTS PASSED")
else:
    print("\nRESULT: ONE OR MORE TESTS FAILED")
    raise SystemExit(1)
