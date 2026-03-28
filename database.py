"""MongoDB connection and collection helpers for EZFOODZ."""
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConfigurationError, OperationFailure
from dotenv import load_dotenv

try:
    import certifi
except ModuleNotFoundError:
    certifi = None

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("MONGO_DB", "ezfoodz")
MONGO_AUTH_SOURCE = os.getenv("MONGO_AUTH_SOURCE", "admin")

client: AsyncIOMotorClient = None
db = None


def _with_default_auth_source(url: str) -> str:
    """Append authSource when the URI has credentials but no explicit auth DB."""
    parsed = urlsplit(url)
    if "@" not in parsed.netloc:
        return url

    query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if "authSource" in query_params:
        return url

    query_params["authSource"] = MONGO_AUTH_SOURCE
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query_params), parsed.fragment)
    )


async def connect_db():
    """Connect to MongoDB. Called on app startup."""
    global client, db
    if not MONGO_URL:
        raise RuntimeError(
            "MONGO_URL is not set. Configure it in your environment before starting the API."
        )

    prepared_url = _with_default_auth_source(MONGO_URL)

    try:
        client_kwargs = {}
        if certifi is not None:
            client_kwargs["tlsCAFile"] = certifi.where()

        client = AsyncIOMotorClient(prepared_url, **client_kwargs)
        db = client[DB_NAME]

        # Validate connectivity/auth before creating indexes.
        await client.admin.command("ping")

        # Create indexes for fast lookups.
        await db.users.create_index("email", unique=True)
        await db.users.create_index("firebase_uid", sparse=True)
        await db.restaurants.create_index("email", unique=True)
        await db.user_sessions.create_index("token", unique=True)
        await db.restaurant_sessions.create_index("token", unique=True)
        await db.orders.create_index("user_id")
        await db.orders.create_index("restaurant_id")
        await db.orders.create_index("payment_id", unique=True, sparse=True)
        await db.payment_intents.create_index("razorpay_order_id", unique=True)
        await db.payment_intents.create_index("user_id")
        await db.monthly_logs.create_index("order_id", unique=True)
        await db.monthly_logs.create_index([("restaurant_id", 1), ("month", 1)])
        print("Connected to MongoDB Atlas")
    except OperationFailure as exc:
        raise RuntimeError(
            "MongoDB authentication failed. Verify MONGO_URL credentials, URL encoding, "
            "and authSource (try MONGO_AUTH_SOURCE=admin for Atlas users)."
        ) from exc
    except ConfigurationError as exc:
        raise RuntimeError(
            "MongoDB URI/configuration is invalid. Check MONGO_URL and TLS options."
        ) from exc


async def close_db():
    """Close MongoDB connection. Called on app shutdown."""
    global client
    if client:
        client.close()
        print("🔌 MongoDB connection closed")


def get_db():
    """Get the database instance."""
    return db


async def get_next_id(collection_name: str) -> int:
    """Auto-increment integer ID for a collection (mimics SQLite AUTOINCREMENT)."""
    result = await db.counters.find_one_and_update(
        {"_id": collection_name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    return result["seq"]
