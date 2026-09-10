import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, HTTPException, Depends, status
from pymongo.errors import PyMongoError, DuplicateKeyError

from backend.app.schemas import TransactionCreate, TransactionResponse, TransactionStatus
from backend.app.database import get_transactions_collection

router = APIRouter(
    prefix="/api/transactions",
    tags=["Transactions"]
)

def generate_transaction_id() -> str:
    """Generate a unique human-readable transaction ID (e.g. TXN-A1B2C3D4E5F6)."""
    return f"TXN-{uuid.uuid4().hex[:12].upper()}"

@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(payload: TransactionCreate, collection=Depends(get_transactions_collection)):
    """
    Create a new payment transaction record.
    - Generates unique transaction ID
    - Sets initial status to CREATED
    - Saves document to MongoDB
    """
    txn_id = generate_transaction_id()
    now = datetime.now(timezone.utc)
    
    doc = {
        "transaction_id": txn_id,
        "amount": round(payload.amount, 2),
        "currency": payload.currency.upper(),
        "status": TransactionStatus.CREATED.value,
        "created_at": now,
        "updated_at": now
    }
    
    try:
        collection.insert_one(doc)
    except DuplicateKeyError:
        txn_id = generate_transaction_id()
        doc["transaction_id"] = txn_id
        collection.insert_one(doc)
    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while saving transaction: {str(err)}"
        )
        
    return doc

@router.get("", response_model=List[TransactionResponse])
def get_all_transactions(collection=Depends(get_transactions_collection)):
    """
    Retrieve all payment transactions.
    """
    try:
        cursor = collection.find({}, {"_id": 0})
        return list(cursor)
    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while retrieving transactions: {str(err)}"
        )

@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction_by_id(transaction_id: str, collection=Depends(get_transactions_collection)):
    """
    Retrieve a single transaction by its transaction_id.
    """
    try:
        doc = collection.find_one({"transaction_id": transaction_id}, {"_id": 0})
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction with ID '{transaction_id}' not found."
            )
        return doc
    except HTTPException:
        raise
    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while retrieving transaction: {str(err)}"
        )
