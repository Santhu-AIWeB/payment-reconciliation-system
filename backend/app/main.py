from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.database import init_db
from backend.app.events.service import init_event_indexes
from backend.app.routers import (
    audit,
    transactions,
    events,
    payment_links,
    gateway,
    bank,
    reconciliation,
    refund,
    retry,
    dashboard,
    ai,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown.
    """
    init_db()
    init_event_indexes()
    yield


app = FastAPI(
    title="Payment Failure & Reconciliation System",
    description=(
        "Backend API for detecting and resolving payment "
        "inconsistencies between payment gateway and bank records."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# =========================================================
# CORS
# =========================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "https://payment-reconciliation-system-m43u.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# ROUTERS
# =========================================================

app.include_router(transactions.router)
app.include_router(gateway.router)
app.include_router(bank.router)
app.include_router(reconciliation.router)
app.include_router(refund.router)
app.include_router(retry.router)
app.include_router(events.router)
app.include_router(dashboard.router)
app.include_router(payment_links.router)
app.include_router(audit.router)
app.include_router(ai.router)


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health_check():
    """
    Health check endpoint.
    """
    return {
        "status": "healthy",
        "service": "payment-reconciliation-backend",
        "step": "8B - Customer Payment Page",
    }
