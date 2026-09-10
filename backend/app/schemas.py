from enum import Enum
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class TransactionStatus(str, Enum):
    CREATED = "CREATED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class TransactionCreate(BaseModel):
    amount: float = Field(
        ...,
        gt=0,
        description="Transaction amount, must be greater than 0",
    )
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
        description="3-letter currency code (e.g., INR, USD)",
    )


class TransactionResponse(BaseModel):
    transaction_id: str
    amount: float
    currency: str
    status: TransactionStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GatewayOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class GatewayProcessRequest(BaseModel):
    transaction_id: str = Field(
        ...,
        description="Unique transaction ID to process",
    )
    outcome: GatewayOutcome


class GatewayProcessResponse(BaseModel):
    transaction_id: str
    gateway_reference: str
    amount: float
    status: GatewayOutcome
    response_message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BankOutcome(str, Enum):
    DEBITED = "DEBITED"
    NOT_DEBITED = "NOT_DEBITED"
    DELAYED = "DELAYED"


class BankProcessRequest(BaseModel):
    transaction_id: str = Field(
        ...,
        description="Unique transaction ID to process",
    )
    outcome: BankOutcome


class BankProcessResponse(BaseModel):
    transaction_id: str
    bank_reference: str
    amount: float
    status: BankOutcome
    response_message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReconciliationStatus(str, Enum):
    MATCHED = "MATCHED"
    MISMATCH = "MISMATCH"
    PENDING = "PENDING"
    DUPLICATE = "DUPLICATE"


class ActionRequired(str, Enum):
    NONE = "NONE"
    REFUND = "REFUND"
    RETRY = "RETRY"
    INVESTIGATE = "INVESTIGATE"
    WAIT = "WAIT"
    BLOCK = "BLOCK"


class ReconciliationRequest(BaseModel):
    transaction_id: str = Field(
        ...,
        description="Transaction ID to reconcile",
    )


class ReconciliationResponse(BaseModel):
    transaction_id: str
    gateway_status: str | None = None
    bank_status: str | None = None
    reconciliation_status: ReconciliationStatus
    reason: str
    action_required: ActionRequired
    created_at: datetime
    resolved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class RefundStatus(str, Enum):
    INITIATED = "INITIATED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DUPLICATE = "DUPLICATE"


class RefundRequest(BaseModel):
    transaction_id: str = Field(
        ...,
        description="Transaction ID to refund",
    )


class RefundResponse(BaseModel):
    transaction_id: str
    refund_reference: str
    amount: float
    status: RefundStatus
    reason: str
    created_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class RetryStatus(str, Enum):
    INITIATED = "INITIATED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    MAX_ATTEMPTS_REACHED = "MAX_ATTEMPTS_REACHED"
    DUPLICATE = "DUPLICATE"


class RetryRequest(BaseModel):
    transaction_id: str = Field(
        ...,
        description="Transaction ID to retry",
    )


class RetryResponse(BaseModel):
    transaction_id: str
    retry_reference: str
    attempt_number: int
    status: RetryStatus
    reason: str
    created_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# Step 8A - Payment Link
# =========================================================

class PaymentLinkStatus(str, Enum):
    ACTIVE = "ACTIVE"
    USED = "USED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class PaymentLinkCreate(BaseModel):
    amount: float = Field(
        ...,
        gt=0,
        description="Payment amount, must be greater than 0",
    )
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
        description="3-letter currency code (e.g., INR, USD)",
    )
    description: str = Field(
        default="Payment",
        min_length=1,
        max_length=200,
        description="Short description shown to the customer",
    )


class PaymentLinkResponse(BaseModel):
    link_id: str
    transaction_id: str
    amount: float
    currency: str
    description: str
    status: PaymentLinkStatus
    payment_url: str
    created_at: datetime
    expires_at: datetime
