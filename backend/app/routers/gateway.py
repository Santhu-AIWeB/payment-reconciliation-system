import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, status
from pymongo.errors import PyMongoError, DuplicateKeyError

from backend.app.schemas import (
    GatewayProcessRequest,
    GatewayProcessResponse,
    GatewayOutcome
)
from backend.app.database import (
    get_transactions_collection,
    get_gateway_transactions_collection
)

router = APIRouter(
    prefix="/api/gateway",
    tags=["Payment Gateway Simulator"]
)

def generate_gateway_reference() -> str:
    """Generate a unique human-readable gateway reference (e.g. GW-A1B2C3D4E5F6)."""
    return f"GW-{uuid.uuid4().hex[:12].upper()}"

RESPONSE_MESSAGES = {
    GatewayOutcome.SUCCESS: "Payment successful",
    GatewayOutcome.FAILED: "Payment failed",
    GatewayOutcome.TIMEOUT: "Gateway timeout"
}

@router.post("/process", response_model=GatewayProcessResponse, status_code=status.HTTP_200_OK)
def process_gateway_payment(
    payload: GatewayProcessRequest,
    transactions_col=Depends(get_transactions_collection),
    gateway_col=Depends(get_gateway_transactions_collection)
):
    """
    Simulate a payment gateway processing request for a given transaction_id.
    - Verifies transaction existence in MongoDB
    - Generates a unique gateway_reference
    - Records outcome in gateway_transactions collection
    - Returns gateway transaction response
    """
    # 1. Verify transaction exists
    try:
        txn = transactions_col.find_one({"transaction_id": payload.transaction_id})
        if not txn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction with ID '{payload.transaction_id}' not found."
            )
    except HTTPException:
        raise
    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while querying transaction: {str(err)}"
        )

    # 2. Extract transaction details
    amount = txn.get("amount", 0.0)
    gateway_ref = generate_gateway_reference()
    now = datetime.now(timezone.utc)
    message = RESPONSE_MESSAGES.get(payload.outcome, "Payment processed")

    # 3. Create gateway transaction document
    gateway_doc = {
        "transaction_id": payload.transaction_id,
        "gateway_reference": gateway_ref,
        "amount": amount,
        "status": payload.outcome.value,
        "response_message": message,
        "created_at": now
    }

    # 4. Insert into gateway_transactions collection
    try:
        gateway_col.insert_one(gateway_doc)
    except DuplicateKeyError:
        gateway_ref = generate_gateway_reference()
        gateway_doc["gateway_reference"] = gateway_ref
        gateway_col.insert_one(gateway_doc)
    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while saving gateway transaction: {str(err)}"
        )

    return gateway_doc
