from datetime import timezone

from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError

from backend.app.config import MONGODB_URI, DB_NAME


client = None
db = None


def init_db():
    """
    Initialize MongoDB client and create necessary indexes.

    MongoDB stores datetimes internally in UTC. Using tz_aware=True
    makes PyMongo return them as timezone-aware UTC datetimes so the
    API/frontend can correctly convert them to the user's local time.
    """
    global client, db

    try:
        client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=3000,
            tz_aware=True,
            tzinfo=timezone.utc,
        )

        db = client[DB_NAME]

        # Transactions: transaction_id must be unique.
        transactions_collection = db["transactions"]
        transactions_collection.create_index(
            [("transaction_id", ASCENDING)],
            unique=True,
        )

        # Gateway: gateway_reference must be unique.
        gateway_transactions_collection = db["gateway_transactions"]
        gateway_transactions_collection.create_index(
            [("gateway_reference", ASCENDING)],
            unique=True,
        )

        # Bank: bank_reference must be unique.
        bank_transactions_collection = db["bank_transactions"]
        bank_transactions_collection.create_index(
            [("bank_reference", ASCENDING)],
            unique=True,
        )

        # Reconciliation: only one reconciliation record per transaction.
        reconciliations_collection = db["reconciliations"]
        reconciliations_collection.create_index(
            [("transaction_id", ASCENDING)],
            unique=True,
        )

        # Refund: only one refund record per transaction.
        refunds_collection = db["refunds"]
        refunds_collection.create_index(
            [("refund_reference", ASCENDING)],
            unique=True,
        )
        refunds_collection.create_index(
            [("transaction_id", ASCENDING)],
            unique=True,
        )

        # Retry: multiple attempts are allowed, but each attempt number
        # can exist only once for a given transaction.
        retry_attempts_collection = db["retry_attempts"]
        retry_attempts_collection.create_index(
            [("retry_reference", ASCENDING)],
            unique=True,
        )
        retry_attempts_collection.create_index(
            [("transaction_id", ASCENDING), ("attempt_number", ASCENDING)],
            unique=True,
        )

        # Payment links: link_id must be unique.
        payment_links_collection = db["payment_links"]
        payment_links_collection.create_index(
            [("link_id", ASCENDING)],
            unique=True,
        )
        payment_links_collection.create_index(
            [("transaction_id", ASCENDING)]
        )

        print(f"[INFO] Connected to MongoDB database '{DB_NAME}' successfully.")

    except PyMongoError as err:
        print(f"[WARNING] MongoDB connection failed: {err}")


def get_db():
    global db

    if db is None:
        init_db()

    return db


def get_transactions_collection():
    return get_db()["transactions"]


def get_gateway_transactions_collection():
    return get_db()["gateway_transactions"]


def get_bank_transactions_collection():
    return get_db()["bank_transactions"]


def get_reconciliations_collection():
    return get_db()["reconciliations"]


def get_refunds_collection():
    return get_db()["refunds"]


def get_retry_attempts_collection():
    return get_db()["retry_attempts"]


def get_payment_links_collection():
    return get_db()["payment_links"]
