import csv
import os
from datetime import datetime, timezone

from database import get_db, get_next_id


def _month_key(now: datetime) -> str:
    return now.strftime("%Y-%m")


def _csv_path(month: str, restaurant_id: int) -> str:
    folder = os.path.join("monthly logs", month)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"restaurant_{restaurant_id}.csv")


def _append_csv_row(path: str, row: dict):
    file_exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "log_id",
            "order_id",
            "restaurant_id",
            "user_id",
            "gross_amount",
            "payment_id",
            "completed_at",
            "month",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


async def log_completed_order(order: dict):
    """Persist a completed transaction once when an order reaches 'given'."""
    db = get_db()

    # Idempotency guard: if this order is already logged, do nothing.
    existing = await db.monthly_logs.find_one({"order_id": order["id"]}, {"_id": 1})
    if existing:
        return

    now = datetime.now(timezone.utc)
    month = _month_key(now)
    log_id = await get_next_id("monthly_logs")

    doc = {
        "id": log_id,
        "order_id": order["id"],
        "restaurant_id": order["restaurant_id"],
        "user_id": order["user_id"],
        "gross_amount": float(order["total"]),
        "payment_id": order.get("payment_id", ""),
        "month": month,
        "completed_at": now.strftime("%Y-%m-%d %H:%M:%S"),
    }

    await db.monthly_logs.insert_one(doc)

    csv_row = {
        "log_id": doc["id"],
        "order_id": doc["order_id"],
        "restaurant_id": doc["restaurant_id"],
        "user_id": doc["user_id"],
        "gross_amount": doc["gross_amount"],
        "payment_id": doc["payment_id"],
        "completed_at": doc["completed_at"],
        "month": doc["month"],
    }

    _append_csv_row(_csv_path(month, order["restaurant_id"]), csv_row)
