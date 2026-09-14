import json
import time
import urllib.request
import urllib.error


BACKEND_BASE = "http://localhost:8000"
GATEWAY_BASE = "http://localhost:8002"


CASES = [
    {
        "name": "FAILED + DEBITED",
        "amount": 101,
        "gateway": "FAILED",
        "bank": "DEBITED",
        "expected_rec": "MISMATCH",
        "expected_action": "REFUND",
        "automation": "REFUND",
    },
    {
        "name": "SUCCESS + NOT_DEBITED",
        "amount": 102,
        "gateway": "SUCCESS",
        "bank": "NOT_DEBITED",
        "expected_rec": "MISMATCH",
        "expected_action": "RETRY",
        "automation": "RETRY",
    },
    {
        "name": "TIMEOUT + DEBITED",
        "amount": 103,
        "gateway": "TIMEOUT",
        "bank": "DEBITED",
        "expected_rec": "MISMATCH",
        "expected_action": "INVESTIGATE",
        "automation": "INVESTIGATE",
    },
    {
        "name": "TIMEOUT + NOT_DEBITED",
        "amount": 104,
        "gateway": "TIMEOUT",
        "bank": "NOT_DEBITED",
        "expected_rec": "PENDING",
        "expected_action": "RETRY",
        "automation": "RETRY",
    },
    {
        "name": "SUCCESS + DELAYED",
        "amount": 105,
        "gateway": "SUCCESS",
        "bank": "DELAYED",
        "expected_rec": "PENDING",
        "expected_action": "WAIT",
        "automation": "WAIT",
    },
]


def request(base, method, path, payload=None, timeout=15):
    data = None
    headers = {}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        base + path,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")

            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                body = raw

        return response.status, body

    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")

        try:
            body = json.loads(raw)
        except Exception:
            body = raw

        return e.code, body

    except Exception as e:
        return 0, {"error": str(e)}


def get_backend(path):
    return request(BACKEND_BASE, "GET", path)


def post_backend(path, payload):
    return request(BACKEND_BASE, "POST", path, payload)


def get_gateway(path):
    return request(GATEWAY_BASE, "GET", path)


def post_gateway(path, payload):
    return request(GATEWAY_BASE, "POST", path, payload)


def check(condition, message):
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {message}")
    return condition


def get_events_for_transaction(transaction_id):
    status, body = get_backend("/api/events?limit=500")

    if status != 200:
        return status, []

    if isinstance(body, dict):
        events = body.get("events", [])
    elif isinstance(body, list):
        events = body
    else:
        events = []

    filtered = [
        event
        for event in events
        if event.get("transaction_id") == transaction_id
    ]

    return status, filtered


def wait_for_reconciliation_event(
    transaction_id,
    expected_action,
    expected_rec,
    timeout=15,
):
    """
    IMPORTANT:
    We use the RECONCILIATION_REQUIRED event because its payload
    preserves the ORIGINAL reconciliation action.

    The reconciliation database record may later change:
        RETRY   -> NONE
        REFUND  -> NONE

    after the automatic workflow succeeds.
    """

    deadline = time.time() + timeout

    while time.time() < deadline:
        status, events = get_events_for_transaction(transaction_id)

        if status == 200:
            for event in events:
                if event.get("event_type") != "RECONCILIATION_REQUIRED":
                    continue

                payload = event.get("payload") or {}

                actual_rec = payload.get("reconciliation_status")
                actual_action = payload.get("action_required")

                if (
                    actual_rec == expected_rec
                    and actual_action == expected_action
                ):
                    return True, event

        time.sleep(0.5)

    return False, None


def get_dashboard_detail(transaction_id):
    return get_backend(f"/api/dashboard/transactions/{transaction_id}")


def wait_for_dashboard_detail(transaction_id, timeout=15):
    deadline = time.time() + timeout

    while time.time() < deadline:
        status, detail = get_dashboard_detail(transaction_id)

        if status == 200 and isinstance(detail, dict):
            transaction = detail.get("transaction")
            reconciliation = detail.get("reconciliation")

            if transaction and reconciliation:
                return True, detail

        time.sleep(0.5)

    return False, None


def wait_for_automatic_workflow(
    transaction_id,
    automation,
    timeout=15,
):
    """
    Validate the FINAL state after the worker has processed
    the reconciliation event.
    """

    deadline = time.time() + timeout

    while time.time() < deadline:
        status, detail = get_dashboard_detail(transaction_id)

        if status == 200 and isinstance(detail, dict):
            transaction = detail.get("transaction") or {}
            reconciliation = detail.get("reconciliation") or {}
            refunds = detail.get("refunds") or detail.get("refund")
            retries = detail.get("retries") or []

            final_status = transaction.get("status")
            final_action = reconciliation.get("action_required")
            final_rec = reconciliation.get("reconciliation_status")

            if automation == "REFUND":
                refund_completed = False

                if isinstance(refunds, list):
                    refund_completed = any(
                        refund.get("status") == "COMPLETED"
                        for refund in refunds
                    )
                elif isinstance(refunds, dict):
                    refund_completed = refunds.get("status") == "COMPLETED"

                if (
                    refund_completed
                    and final_status == "RESOLVED"
                    and final_action == "NONE"
                ):
                    return True, detail

            elif automation == "RETRY":
                retry_success = any(
                    retry.get("status") == "SUCCESS"
                    for retry in retries
                    if isinstance(retry, dict)
                )

                if (
                    retry_success
                    and final_status == "RESOLVED"
                    and final_action == "NONE"
                ):
                    return True, detail

            elif automation == "INVESTIGATE":
                if (
                    final_rec == "MISMATCH"
                    and final_action == "INVESTIGATE"
                    and final_status != "RESOLVED"
                ):
                    return True, detail

            elif automation == "WAIT":
                if (
                    final_rec == "PENDING"
                    and final_action == "WAIT"
                ):
                    return True, detail

        time.sleep(0.5)

    return False, None


def validate_lifecycle_events(transaction_id):
    required_events = {
        "PAYMENT_CREATED",
        "GATEWAY_PROCESSED",
        "BANK_PROCESSED",
        "RECONCILIATION_REQUIRED",
    }

    status, events = get_events_for_transaction(transaction_id)

    ok = check(
        status == 200,
        "Event Operations API reachable",
    )

    if not ok:
        return False

    event_types = {
        event.get("event_type")
        for event in events
        if event.get("event_type")
    }

    all_events_present = required_events.issubset(event_types)

    check(
        all_events_present,
        f"Lifecycle events recorded: {sorted(event_types)}",
    )

    all_ok = all_events_present

    for event_type in [
        "RECONCILIATION_REQUIRED",
        "BANK_PROCESSED",
        "GATEWAY_PROCESSED",
        "PAYMENT_CREATED",
    ]:
        matches = [
            event
            for event in events
            if event.get("event_type") == event_type
        ]

        event_exists = len(matches) > 0

        all_ok &= check(
            event_exists,
            f"{event_type} event recorded",
        )

        if not event_exists:
            continue

        event = sorted(
            matches,
            key=lambda x: x.get("created_at", ""),
            reverse=True,
        )[0]

        event_status = event.get("status")

        all_ok &= check(
            event_status == "COMPLETED",
            f"{event_type} event = {event_status}",
        )

        broker_published = event.get("broker_published_at")

        all_ok &= check(
            bool(broker_published),
            f"{event_type} published to RabbitMQ",
        )

    return all_ok


def validate_ai(transaction_id):
    status, ai = get_backend(f"/api/ai/analyze/{transaction_id}")

    ok = check(
        status == 200,
        "AI analysis endpoint works",
    )

    if not ok:
        return False

    model = ai.get("model_type")
    samples = ai.get("training_samples")

    ok &= check(
        model == "isolation_forest",
        f"AI model = {model}",
    )

    ok &= check(
        isinstance(samples, int) and samples >= 10,
        f"AI training samples = {samples}",
    )

    return ok


print("=" * 76)
print("PAYMENT RECONCILIATION - EVENT-DRIVEN FULL SYSTEM TEST")
print("=" * 76)


# ---------------------------------------------------------------------------
# Basic health checks
# ---------------------------------------------------------------------------

status, health = get_backend("/api/dashboard/summary")

if not check(
    status == 200,
    f"Backend reachable: HTTP {status}",
):
    raise SystemExit(1)


status, gateway_docs = get_gateway("/docs")

if not check(
    status == 200,
    "Gateway Server reachable",
):
    raise SystemExit(1)


print("\nTesting 5 fresh event-driven scenarios...\n")


all_passed = True
transaction_ids = []


# ---------------------------------------------------------------------------
# Test scenarios
# ---------------------------------------------------------------------------

for case in CASES:
    print("-" * 76)
    print(case["name"])

    # -----------------------------------------------------------------------
    # 1. Send payment through Gateway
    # -----------------------------------------------------------------------

    status, payment = post_gateway(
        "/api/gateway/test-pay",
        {
            "amount": case["amount"],
            "currency": "INR",
            "account_id": "DUMMY-1001",
            "gateway_outcome": case["gateway"],
            "bank_outcome": case["bank"],
        },
    )

    ok = check(
        status == 200 and "transaction_id" in payment,
        "Gateway test payment accepted",
    )

    all_passed &= ok

    if not ok:
        continue

    txn_id = payment["transaction_id"]
    transaction_ids.append(txn_id)

    print(f"  Transaction: {txn_id}")


    # -----------------------------------------------------------------------
    # 2. Gateway result
    # -----------------------------------------------------------------------

    gateway_result = payment.get("gateway") or {}

    all_passed &= check(
        gateway_result.get("status") == case["gateway"],
        f"Gateway = {case['gateway']}",
    )


    # -----------------------------------------------------------------------
    # 3. Bank result
    # -----------------------------------------------------------------------

    bank_result = payment.get("bank") or {}

    all_passed &= check(
        bank_result.get("status") == case["bank"],
        f"Bank = {case['bank']}",
    )


    # -----------------------------------------------------------------------
    # 4. Wait for RECONCILIATION_REQUIRED event
    #
    # This is the IMPORTANT FIX.
    #
    # We do NOT read action_required from the final dashboard state
    # because RETRY/REFUND may already have changed it to NONE.
    # -----------------------------------------------------------------------

    event_found, reconciliation_event = wait_for_reconciliation_event(
        txn_id,
        case["expected_action"],
        case["expected_rec"],
        timeout=15,
    )

    all_passed &= check(
        event_found,
        "Original reconciliation event available",
    )

    if event_found:
        payload = reconciliation_event.get("payload") or {}

        original_rec = payload.get("reconciliation_status")
        original_action = payload.get("action_required")

        all_passed &= check(
            original_rec == case["expected_rec"],
            (
                f"Original reconciliation = {original_rec} "
                f"(expected {case['expected_rec']})"
            ),
        )

        all_passed &= check(
            original_action == case["expected_action"],
            (
                f"Original action = {original_action} "
                f"(expected {case['expected_action']})"
            ),
        )


    # -----------------------------------------------------------------------
    # 5. Dashboard detail after asynchronous processing
    # -----------------------------------------------------------------------

    detail_found, detail = wait_for_dashboard_detail(
        txn_id,
        timeout=15,
    )

    all_passed &= check(
        detail_found,
        "Dashboard transaction detail available",
    )

    if not detail_found:
        continue


    # -----------------------------------------------------------------------
    # 6. Validate FINAL reconciliation state
    # -----------------------------------------------------------------------

    reconciliation = detail.get("reconciliation") or {}
    final_rec = reconciliation.get("reconciliation_status")
    final_action = reconciliation.get("action_required")

    if case["automation"] == "REFUND":
        # Original action = REFUND
        # Final action becomes NONE after successful refund.

        all_passed &= check(
            final_rec == "MISMATCH",
            f"Final reconciliation = {final_rec}",
        )

        all_passed &= check(
            final_action == "NONE",
            f"Final action = {final_action} after refund",
        )

    elif case["automation"] == "RETRY":
        # Original action = RETRY
        # Final action becomes NONE after successful retry.

        all_passed &= check(
            final_rec in ("MISMATCH", "PENDING"),
            f"Final reconciliation = {final_rec}",
        )

        all_passed &= check(
            final_action == "NONE",
            f"Final action = {final_action} after retry",
        )

    elif case["automation"] == "INVESTIGATE":
        all_passed &= check(
            final_rec == "MISMATCH",
            f"Reconciliation = {final_rec} (expected MISMATCH)",
        )

        all_passed &= check(
            final_action == "INVESTIGATE",
            f"Action = {final_action} (expected INVESTIGATE)",
        )

    elif case["automation"] == "WAIT":
        all_passed &= check(
            final_rec == "PENDING",
            f"Reconciliation = {final_rec} (expected PENDING)",
        )

        all_passed &= check(
            final_action == "WAIT",
            f"Action = {final_action} (expected WAIT)",
        )


    # -----------------------------------------------------------------------
    # 7. Validate automatic/manual workflow
    # -----------------------------------------------------------------------

    workflow_ok, final_detail = wait_for_automatic_workflow(
        txn_id,
        case["automation"],
        timeout=15,
    )

    if case["automation"] == "REFUND":

        all_passed &= check(
            workflow_ok,
            "Automatic refund workflow completed",
        )

        if workflow_ok:
            transaction = final_detail.get("transaction") or {}

            all_passed &= check(
                transaction.get("status") == "RESOLVED",
                "Transaction resolved after automatic refund",
            )

    elif case["automation"] == "RETRY":

        all_passed &= check(
            workflow_ok,
            "Automatic retry workflow completed",
        )

        if workflow_ok:
            transaction = final_detail.get("transaction") or {}

            all_passed &= check(
                transaction.get("status") == "RESOLVED",
                "Transaction final status = RESOLVED",
            )

    elif case["automation"] == "INVESTIGATE":

        all_passed &= check(
            workflow_ok,
            "Investigation case remains a mismatch",
        )

        if workflow_ok:
            transaction = final_detail.get("transaction") or {}

            all_passed &= check(
                transaction.get("status") != "RESOLVED",
                "Transaction remains available for manual investigation",
            )

    elif case["automation"] == "WAIT":

        all_passed &= check(
            workflow_ok,
            "Delayed bank case remains pending",
        )

        if workflow_ok:
            reconciliation = final_detail.get("reconciliation") or {}

            all_passed &= check(
                reconciliation.get("action_required") == "WAIT",
                "Delayed bank case requires WAIT",
            )


    # -----------------------------------------------------------------------
    # 8. Event lifecycle validation
    # -----------------------------------------------------------------------

    lifecycle_ok = validate_lifecycle_events(txn_id)
    all_passed &= lifecycle_ok


    # -----------------------------------------------------------------------
    # 9. AI validation
    # -----------------------------------------------------------------------

    ai_ok = validate_ai(txn_id)
    all_passed &= ai_ok


# ---------------------------------------------------------------------------
# Final result
# ---------------------------------------------------------------------------

print("\n" + "=" * 76)
print("FINAL RESULT")
print("=" * 76)


status, summary = get_backend("/api/dashboard/summary")

if status == 200:
    print(json.dumps(summary, indent=2))
else:
    print(json.dumps(
        {
            "error": "Unable to fetch dashboard summary",
            "http_status": status,
        },
        indent=2,
    ))


print("\nTest transaction IDs:")

for txn_id in transaction_ids:
    print(f"  - {txn_id}")


print("\n" + "=" * 76)

if all_passed:
    print("RESULT: ALL TESTS PASSED")
else:
    print("RESULT: ONE OR MORE TESTS FAILED")

print("=" * 76)


raise SystemExit(0 if all_passed else 1)