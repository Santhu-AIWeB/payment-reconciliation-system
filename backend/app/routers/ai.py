"""
AI endpoints for anomaly/risk analysis.
"""

from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import PyMongoError

from backend.app.database import (
    get_bank_transactions_collection,
    get_gateway_transactions_collection,
    get_reconciliations_collection,
    get_transactions_collection,
)
from backend.app.ai_service import MODEL_FEATURES, analyze_transaction, build_feature_row


router = APIRouter(
    prefix="/api/ai",
    tags=["AI Analysis"],
)


@router.get("/analyze/{transaction_id}")
def analyze(
    transaction_id: str,
    transactions_col=Depends(get_transactions_collection),
    gateway_col=Depends(get_gateway_transactions_collection),
    bank_col=Depends(get_bank_transactions_collection),
    reconciliation_col=Depends(get_reconciliations_collection),
):
    """
    Analyze one simulated transaction for anomalous behavior.

    The AI layer never changes payment state and never triggers refunds/retries.
    It only produces an analysis for the admin/investigation experience.
    """
    try:
        txn = transactions_col.find_one(
            {"transaction_id": transaction_id},
            {"_id": 0},
        )
        if not txn:
            raise HTTPException(
                status_code=404,
                detail=f"Transaction with ID '{transaction_id}' not found.",
            )

        gateway = gateway_col.find_one(
            {"transaction_id": transaction_id},
            {"_id": 0},
        )
        bank = bank_col.find_one(
            {"transaction_id": transaction_id},
            {"_id": 0},
        )
        reconciliation = reconciliation_col.find_one(
            {"transaction_id": transaction_id},
            {"_id": 0},
        )

        # Build historical feature rows from existing records. This does not mutate
        # the database and intentionally reuses the current simulation data.
        historical_rows: list[dict[str, float]] = []

        for history_txn in transactions_col.find({}, {"_id": 0}):
            history_id = history_txn.get("transaction_id")
            if not history_id:
                continue

            history_gateway = gateway_col.find_one(
                {"transaction_id": history_id},
                {"_id": 0},
            )
            history_bank = bank_col.find_one(
                {"transaction_id": history_id},
                {"_id": 0},
            )
            history_rec = reconciliation_col.find_one(
                {"transaction_id": history_id},
                {"_id": 0},
            )

            row = build_feature_row(
                history_txn,
                history_gateway,
                history_bank,
                history_rec,
            )
            historical_rows.append(row)

        # Keep the feature ordering explicit and stable for the ML model.
        historical_rows = [
            {feature: float(row.get(feature, 0.0)) for feature in MODEL_FEATURES}
            for row in historical_rows
        ]

        return analyze_transaction(
            transaction_id=transaction_id,
            txn=txn,
            gateway=gateway,
            bank=bank,
            reconciliation=reconciliation,
            historical_feature_rows=historical_rows,
        )

    except HTTPException:
        raise
    except PyMongoError as err:
        raise HTTPException(
            status_code=500,
            detail=f"Database error during AI analysis: {str(err)}",
        )
