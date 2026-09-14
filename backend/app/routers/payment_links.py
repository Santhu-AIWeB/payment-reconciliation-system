import os
import uuid
from datetime import datetime, timedelta, timezone

from backend.app.events.schemas import EventType, PaymentEvent
from backend.app.events.publisher import DualWriteEventPublisher

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError, PyMongoError

from backend.app.database import (
    get_payment_links_collection,
    get_transactions_collection,
    get_gateway_transactions_collection,
    get_bank_transactions_collection,
    get_reconciliations_collection,
)
from backend.app.schemas import (
    PaymentLinkCreate,
    PaymentLinkResponse,
    PaymentLinkStatus,
    TransactionStatus,
    GatewayOutcome,
    BankOutcome,
    ReconciliationStatus,
    ActionRequired,
)


router = APIRouter(
    prefix="/api/payment-links",
    tags=["Payment Links"],
)


FRONTEND_BASE_URL = os.getenv(
    "FRONTEND_BASE_URL",
    "http://localhost:5173",
).rstrip("/")


PAYMENT_LINK_EXPIRY_HOURS = 24


class PaymentProcessRequest(BaseModel):
    """Customer payment simulation request."""

    outcome: GatewayOutcome


def generate_link_id() -> str:
    return f"PAY-{uuid.uuid4().hex[:12].upper()}"


def generate_transaction_id() -> str:
    return f"TXN-{uuid.uuid4().hex[:12].upper()}"


def generate_gateway_reference() -> str:
    return f"GTW-{uuid.uuid4().hex[:12].upper()}"


def generate_bank_reference() -> str:
    return f"BNK-{uuid.uuid4().hex[:12].upper()}"


def generate_reconciliation_id() -> str:
    return f"REC-{uuid.uuid4().hex[:12].upper()}"


def build_payment_url(link_id: str) -> str:
    return f"{FRONTEND_BASE_URL}/pay/{link_id}"


def normalize_utc_datetime(value: datetime) -> datetime:
    """Normalize MongoDB datetimes to timezone-aware UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def simulation_state(outcome: GatewayOutcome):
    """Map customer-selected outcome to gateway, bank and reconciliation states."""

    if outcome == GatewayOutcome.SUCCESS:
        return {
            "gateway_status": GatewayOutcome.SUCCESS.value,
            "bank_status": BankOutcome.DEBITED.value,
            "reconciliation_status": ReconciliationStatus.MATCHED.value,
            "action_required": ActionRequired.NONE.value,
            "transaction_status": TransactionStatus.SUCCESS.value,
            "gateway_message": "Payment gateway reported success.",
            "bank_message": "Bank simulator debited the payment amount.",
            "reason": "Gateway SUCCESS and bank DEBITED match.",
        }

    if outcome == GatewayOutcome.FAILED:
        return {
            "gateway_status": GatewayOutcome.FAILED.value,
            "bank_status": BankOutcome.DEBITED.value,
            "reconciliation_status": ReconciliationStatus.MISMATCH.value,
            "action_required": ActionRequired.REFUND.value,
            "transaction_status": TransactionStatus.FAILED.value,
            "gateway_message": "Payment gateway reported failure.",
            "bank_message": "Bank simulator debited the payment amount.",
            "reason": "Gateway FAILED but bank DEBITED. Refund is required.",
        }

    return {
        "gateway_status": GatewayOutcome.TIMEOUT.value,
        "bank_status": BankOutcome.DEBITED.value,
        "reconciliation_status": ReconciliationStatus.MISMATCH.value,
        "action_required": ActionRequired.INVESTIGATE.value,
        "transaction_status": TransactionStatus.PENDING.value,
        "gateway_message": "Gateway response timed out.",
        "bank_message": "Bank simulator shows the amount as debited.",
        "reason": "Gateway TIMEOUT while bank shows DEBITED. Investigation required.",
    }


@router.post(
    "",
    response_model=PaymentLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payment_link(
    payload: PaymentLinkCreate,
    links_collection=Depends(get_payment_links_collection),
    transactions_collection=Depends(get_transactions_collection),
):
    """Create a payment link and its underlying transaction."""

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=PAYMENT_LINK_EXPIRY_HOURS)

    transaction_id = generate_transaction_id()
    link_id = generate_link_id()

    transaction_doc = {
        "transaction_id": transaction_id,
        "amount": round(payload.amount, 2),
        "currency": payload.currency.upper(),
        "status": TransactionStatus.CREATED.value,
        "created_at": now,
        "updated_at": now,
    }

    link_doc = {
        "link_id": link_id,
        "transaction_id": transaction_id,
        "amount": round(payload.amount, 2),
        "currency": payload.currency.upper(),
        "description": payload.description,
        "status": PaymentLinkStatus.ACTIVE.value,
        "payment_url": build_payment_url(link_id),
        "created_at": now,
        "expires_at": expires_at,
    }

    try:
        transactions_collection.insert_one(transaction_doc)
        links_collection.insert_one(link_doc)

    except DuplicateKeyError:
        try:
            transactions_collection.delete_one(
                {"transaction_id": transaction_id}
            )
        except PyMongoError:
            pass

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to create a unique payment link. Please retry.",
        )

    except PyMongoError as err:
        try:
            transactions_collection.delete_one(
                {"transaction_id": transaction_id}
            )
        except PyMongoError:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while creating payment link: {str(err)}",
        )

    # Phase 2H:
    # Persist the PAYMENT_CREATED event in MongoDB
    # and publish the same event to RabbitMQ.
    event = PaymentEvent(
        event_id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
        event_type=EventType.PAYMENT_CREATED,
        transaction_id=transaction_id,
        payload={
            "amount": transaction_doc["amount"],
            "currency": transaction_doc["currency"],
            "link_id": link_id,
        },
        correlation_id=transaction_id,
    )

    DualWriteEventPublisher().publish(event)

    return link_doc


@router.get(
    "",
    response_model=list[PaymentLinkResponse],
)
def get_all_payment_links(
    collection=Depends(get_payment_links_collection),
):
    """Retrieve all payment links for the admin dashboard."""

    try:
        docs = collection.find(
            {},
            {"_id": 0},
        ).sort("created_at", -1)

        return list(docs)

    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while retrieving payment links: {str(err)}",
        )


@router.get(
    "/{link_id}",
    response_model=PaymentLinkResponse,
)
def get_payment_link(
    link_id: str,
    collection=Depends(get_payment_links_collection),
):
    """Retrieve a payment link for the customer payment page."""

    try:
        doc = collection.find_one(
            {"link_id": link_id},
            {"_id": 0},
        )

        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment link '{link_id}' not found.",
            )

        now = datetime.now(timezone.utc)
        expires_at = doc.get("expires_at")

        if expires_at is not None:
            expires_at = normalize_utc_datetime(expires_at)

            if (
                doc["status"] == PaymentLinkStatus.ACTIVE.value
                and expires_at <= now
            ):
                collection.update_one(
                    {"link_id": link_id},
                    {
                        "$set": {
                            "status": PaymentLinkStatus.EXPIRED.value
                        }
                    },
                )

                doc["status"] = PaymentLinkStatus.EXPIRED.value

        return doc

    except HTTPException:
        raise

    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while retrieving payment link: {str(err)}",
        )


@router.post("/{link_id}/pay")
def process_payment(
    link_id: str,
    payload: PaymentProcessRequest,
    links_collection=Depends(get_payment_links_collection),
    transactions_collection=Depends(get_transactions_collection),
    gateway_collection=Depends(get_gateway_transactions_collection),
    bank_collection=Depends(get_bank_transactions_collection),
    reconciliation_collection=Depends(get_reconciliations_collection),
):
    """
    Process a customer payment in simulation mode.

    Selected outcome controls the gateway result while the simulator
    intentionally uses a DEBITED bank result for the three Step 8B cases:

      SUCCESS -> MATCHED
      FAILED  -> MISMATCH + REFUND
      TIMEOUT -> MISMATCH + INVESTIGATE
    """

    try:
        link = links_collection.find_one(
            {"link_id": link_id},
            {"_id": 0},
        )

        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment link '{link_id}' not found.",
            )

        if link.get("status") != PaymentLinkStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Payment link is "
                    f"{link.get('status', 'UNAVAILABLE')} "
                    f"and cannot be paid."
                ),
            )

        now = datetime.now(timezone.utc)
        expires_at = link.get("expires_at")

        if expires_at is not None:
            expires_at = normalize_utc_datetime(expires_at)

            if expires_at <= now:
                links_collection.update_one(
                    {"link_id": link_id},
                    {
                        "$set": {
                            "status": PaymentLinkStatus.EXPIRED.value
                        }
                    },
                )

                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Payment link has expired.",
                )

        transaction_id = link["transaction_id"]
        state = simulation_state(payload.outcome)

        transaction = transactions_collection.find_one(
            {"transaction_id": transaction_id},
            {"_id": 0},
        )

        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction '{transaction_id}' not found.",
            )

        amount = round(float(link["amount"]), 2)

        gateway_doc = {
            "transaction_id": transaction_id,
            "gateway_reference": generate_gateway_reference(),
            "amount": amount,
            "status": state["gateway_status"],
            "response_message": state["gateway_message"],
            "created_at": now,
        }

        bank_doc = {
            "transaction_id": transaction_id,
            "bank_reference": generate_bank_reference(),
            "amount": amount,
            "status": state["bank_status"],
            "response_message": state["bank_message"],
            "created_at": now,
        }

        reconciliation_doc = {
            "transaction_id": transaction_id,
            "reconciliation_id": generate_reconciliation_id(),
            "gateway_status": state["gateway_status"],
            "bank_status": state["bank_status"],
            "reconciliation_status": state["reconciliation_status"],
            "reason": state["reason"],
            "action_required": state["action_required"],
            "created_at": now,
            "resolved_at": (
                now
                if state["reconciliation_status"]
                == ReconciliationStatus.MATCHED.value
                else None
            ),
        }

        gateway_collection.insert_one(gateway_doc)
        bank_collection.insert_one(bank_doc)
        reconciliation_collection.insert_one(reconciliation_doc)

        # Phase 2H:
        # Publish gateway, bank and reconciliation events
        # through the dual-write publisher.
        publisher = DualWriteEventPublisher()

        gateway_event = PaymentEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
            event_type=EventType.GATEWAY_PROCESSED,
            transaction_id=transaction_id,
            payload={
                "gateway_reference": gateway_doc["gateway_reference"],
                "amount": gateway_doc["amount"],
                "status": gateway_doc["status"],
                "response_message": gateway_doc["response_message"],
            },
            correlation_id=transaction_id,
        )

        publisher.publish(gateway_event)

        bank_event = PaymentEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
            event_type=EventType.BANK_PROCESSED,
            transaction_id=transaction_id,
            payload={
                "bank_reference": bank_doc["bank_reference"],
                "amount": bank_doc["amount"],
                "status": bank_doc["status"],
                "response_message": bank_doc["response_message"],
            },
            correlation_id=transaction_id,
        )

        publisher.publish(bank_event)

        reconciliation_event = PaymentEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
            event_type=EventType.RECONCILIATION_REQUIRED,
            transaction_id=transaction_id,
            payload={
                "gateway_status": reconciliation_doc["gateway_status"],
                "bank_status": reconciliation_doc["bank_status"],
                "reconciliation_status": (
                    reconciliation_doc["reconciliation_status"]
                ),
                "action_required": reconciliation_doc["action_required"],
                "reason": reconciliation_doc["reason"],
            },
            correlation_id=transaction_id,
        )

        publisher.publish(reconciliation_event)

        # FAILED payment → REFUND_REQUIRED
        if state["action_required"] == ActionRequired.REFUND.value:
            refund_event = PaymentEvent(
                event_id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
                event_type=EventType.REFUND_REQUIRED,
                transaction_id=transaction_id,
                payload={
                    "amount": amount,
                    "reason": state["reason"],
                    "gateway_status": state["gateway_status"],
                    "bank_status": state["bank_status"],
                },
                correlation_id=transaction_id,
            )

            publisher.publish(refund_event)

        # TIMEOUT payment → INVESTIGATION_REQUIRED
        if state["action_required"] == ActionRequired.INVESTIGATE.value:
            investigation_event = PaymentEvent(
                event_id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
                event_type=EventType.INVESTIGATION_REQUIRED,
                transaction_id=transaction_id,
                payload={
                    "amount": amount,
                    "reason": state["reason"],
                    "gateway_status": state["gateway_status"],
                    "bank_status": state["bank_status"],
                },
                correlation_id=transaction_id,
            )

            publisher.publish(investigation_event)

        transactions_collection.update_one(
            {"transaction_id": transaction_id},
            {
                "$set": {
                    "status": state["transaction_status"],
                    "updated_at": now,
                }
            },
        )

        links_collection.update_one(
            {"link_id": link_id},
            {
                "$set": {
                    "status": PaymentLinkStatus.USED.value,
                    "used_at": now,
                }
            },
        )

        return {
            "success": True,
            "simulation_mode": True,
            "link_id": link_id,
            "transaction_id": transaction_id,
            "amount": amount,
            "currency": link["currency"],
            "gateway": {
                "status": gateway_doc["status"],
                "reference": gateway_doc["gateway_reference"],
                "message": gateway_doc["response_message"],
            },
            "bank": {
                "status": bank_doc["status"],
                "reference": bank_doc["bank_reference"],
                "message": bank_doc["response_message"],
            },
            "reconciliation": {
                "status": reconciliation_doc["reconciliation_status"],
                "action_required": reconciliation_doc["action_required"],
                "reason": reconciliation_doc["reason"],
            },
            "transaction_status": state["transaction_status"],
            "processed_at": now,
        }

    except HTTPException:
        raise

    except DuplicateKeyError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Payment processing created a duplicate record: {str(err)}",
        )

    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while processing payment: {str(err)}",
        )