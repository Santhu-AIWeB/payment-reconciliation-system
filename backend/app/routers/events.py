from fastapi import APIRouter, HTTPException, status

from backend.app.events.consumer import process_next_event, process_pending_events

router = APIRouter(
    prefix="/api/events",
    tags=["Event Consumer"],
)


@router.post("/process-next")
def process_next():
    """
    Process one pending event.

    This endpoint is intentionally explicit for Phase 2C.
    It does not start an automatic background worker.
    """

    try:
        processed = process_next_event()

        if not processed:
            return {
                "success": True,
                "processed": False,
                "message": "No pending event available.",
            }

        return {
            "success": True,
            "processed": True,
            "message": "One pending event processed successfully.",
        }

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Event processing failed: {str(exc)}",
        )


@router.post("/process-pending")
def process_pending(max_events: int = 10):
    """
    Process up to max_events pending events.
    """

    if max_events < 1 or max_events > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="max_events must be between 1 and 100.",
        )

    try:
        processed_count = process_pending_events(max_events)

        return {
            "success": True,
            "processed_count": processed_count,
            "max_events": max_events,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Event batch processing failed: {str(exc)}",
        )
