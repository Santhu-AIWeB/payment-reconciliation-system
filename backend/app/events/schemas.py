from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    PAYMENT_CREATED = "PAYMENT_CREATED"
    GATEWAY_PROCESSED = "GATEWAY_PROCESSED"
    BANK_PROCESSED = "BANK_PROCESSED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    REFUND_REQUIRED = "REFUND_REQUIRED"
    RETRY_REQUIRED = "RETRY_REQUIRED"
    INVESTIGATION_REQUIRED = "INVESTIGATION_REQUIRED"


class EventStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PaymentEvent(BaseModel):
    event_id: str = Field(..., min_length=1)
    event_type: EventType
    transaction_id: str = Field(..., min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    status: EventStatus = EventStatus.PENDING
    correlation_id: str = Field(..., min_length=1)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    processed_at: datetime | None = None
    retry_count: int = Field(default=0, ge=0)
    error_message: str | None = None
