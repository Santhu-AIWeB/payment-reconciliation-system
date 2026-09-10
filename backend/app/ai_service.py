"""
AI anomaly detection service for the Payment Failure & Reconciliation System.

This is intentionally an explainable first ML layer:
- Reads historical transaction + gateway + bank + reconciliation records.
- Builds numeric features from the existing simulated payment lifecycle.
- Uses IsolationForest when enough history exists.
- Falls back to a transparent rule-based risk score when the dataset is too small
  for a useful unsupervised model.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest


MODEL_FEATURES = [
    "amount",
    "gateway_failed",
    "gateway_timeout",
    "bank_debited",
    "bank_delayed",
    "reconciliation_mismatch",
    "reconciliation_pending",
    "action_refund",
    "action_retry",
    "action_investigate",
]


def _status(doc: dict[str, Any] | None, key: str) -> str:
    if not doc:
        return ""
    value = doc.get(key)
    return str(value).upper() if value is not None else ""


def build_feature_row(
    txn: dict[str, Any],
    gateway: dict[str, Any] | None,
    bank: dict[str, Any] | None,
    reconciliation: dict[str, Any] | None,
) -> dict[str, float]:
    gateway_status = _status(gateway, "status")
    bank_status = _status(bank, "status")
    rec_status = _status(reconciliation, "reconciliation_status")
    action = _status(reconciliation, "action_required")

    return {
        "amount": float(txn.get("amount") or 0),
        "gateway_failed": 1.0 if gateway_status == "FAILED" else 0.0,
        "gateway_timeout": 1.0 if gateway_status == "TIMEOUT" else 0.0,
        "bank_debited": 1.0 if bank_status == "DEBITED" else 0.0,
        "bank_delayed": 1.0 if bank_status == "DELAYED" else 0.0,
        "reconciliation_mismatch": 1.0 if rec_status == "MISMATCH" else 0.0,
        "reconciliation_pending": 1.0 if rec_status == "PENDING" else 0.0,
        "action_refund": 1.0 if action == "REFUND" else 0.0,
        "action_retry": 1.0 if action == "RETRY" else 0.0,
        "action_investigate": 1.0 if action == "INVESTIGATE" else 0.0,
    }


def _scenario_explanation(features: dict[str, float]) -> tuple[list[str], str]:
    reasons: list[str] = []

    if features["gateway_failed"] and features["bank_debited"]:
        reasons.append("Gateway FAILED but the bank shows DEBITED.")
        return reasons, "Review for refund / debit mismatch"

    if features["gateway_timeout"] and features["bank_debited"]:
        reasons.append("Gateway TIMEOUT but the bank shows DEBITED.")
        return reasons, "Investigate before allowing another payment attempt"

    if features["gateway_failed"] and not features["bank_debited"]:
        reasons.append("Gateway FAILED and the bank shows no debit.")
        return reasons, "Low-priority exception"

    if features["gateway_timeout"] and not features["bank_debited"]:
        reasons.append("Gateway TIMEOUT and the bank shows no debit.")
        return reasons, "Verify final gateway outcome before retry"

    if features["action_retry"]:
        reasons.append("Reconciliation requires a RETRY action.")
        return reasons, "Review retry eligibility"

    if features["action_investigate"]:
        reasons.append("Reconciliation requires manual INVESTIGATION.")
        return reasons, "High-priority manual review"

    if features["reconciliation_mismatch"]:
        reasons.append("The transaction is marked as a reconciliation mismatch.")
        return reasons, "Review exception details"

    if features["reconciliation_pending"] or features["bank_delayed"]:
        reasons.append("The payment outcome is still pending or delayed.")
        return reasons, "Wait for definitive outcome"

    return ["No payment exception indicators were detected."], "No immediate investigation required"


def _rule_based_assessment(features: dict[str, float]) -> dict[str, Any]:
    score = 0.0

    if features["gateway_failed"] and features["bank_debited"]:
        score += 0.60

    if features["gateway_timeout"] and features["bank_debited"]:
        score += 0.55

    if features["reconciliation_mismatch"]:
        score += 0.20

    if features["reconciliation_pending"]:
        score += 0.10

    if features["action_investigate"]:
        score += 0.20

    if features["bank_delayed"]:
        score += 0.10

    score = min(score, 1.0)

    if score >= 0.75:
        level = "HIGH"
    elif score >= 0.40:
        level = "MEDIUM"
    else:
        level = "LOW"

    reasons, priority = _scenario_explanation(features)

    return {
        "anomaly": score >= 0.40,
        "risk_score": round(score, 4),
        "risk_level": level,
        "reasons": reasons,
        "investigation_priority": priority,
        "model_type": "rule_based_fallback",
    }

def analyze_transaction(
    transaction_id: str,
    txn: dict[str, Any],
    gateway: dict[str, Any] | None,
    bank: dict[str, Any] | None,
    reconciliation: dict[str, Any] | None,
    historical_feature_rows: list[dict[str, float]],
) -> dict[str, Any]:
    features = build_feature_row(txn, gateway, bank, reconciliation)

    # A tiny dataset produces unstable unsupervised results, so use the transparent
    # fallback until we have enough historical transactions.
    if len(historical_feature_rows) < 10:
        assessment = _rule_based_assessment(features)
        assessment.update({
            "transaction_id": transaction_id,
            "features": features,
            "training_samples": len(historical_feature_rows),
        })
        return assessment

    matrix = np.array(
        [
            [row[name] for name in MODEL_FEATURES]
            for row in historical_feature_rows
        ],
        dtype=float,
    )

    model = IsolationForest(
        n_estimators=200,
        contamination="auto",
        random_state=42,
    )
    model.fit(matrix)

    current_vector = np.array(
        [[features[name] for name in MODEL_FEATURES]],
        dtype=float,
    )

    prediction = int(model.predict(current_vector)[0])
    raw_score = float(model.decision_function(current_vector)[0])

    # Convert the model's signed decision score to an easy 0..1 risk score.
    risk_score = float(np.clip(0.5 - raw_score, 0.0, 1.0))
    anomaly = prediction == -1

    if risk_score >= 0.75:
        level = "HIGH"
    elif risk_score >= 0.40:
        level = "MEDIUM"
    else:
        level = "LOW"

    scenario_reasons, priority = _scenario_explanation(features)

    return {
        "transaction_id": transaction_id,
        "anomaly": anomaly,
        "risk_score": round(risk_score, 4),
        "risk_level": level,
        "reasons": scenario_reasons if anomaly else ["No strong anomaly pattern was detected."],
        "investigation_priority": priority,
        "model_type": "isolation_forest",
        "training_samples": len(historical_feature_rows),
        "features": features,
    }
