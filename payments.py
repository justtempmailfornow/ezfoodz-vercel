import os
import random
from datetime import datetime, timezone
from typing import List

import razorpay
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from database import get_db, get_next_id
from orders import get_user_from_token

router = APIRouter(tags=["Payments"])

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")


class OrderItem(BaseModel):
    item_id: int
    quantity: int


class CreatePaymentOrderRequest(BaseModel):
    restaurant_id: int
    items: List[OrderItem]


class VerifyAndPlaceOrderRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


def _rzp_client() -> razorpay.Client:
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Razorpay keys are missing on server. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.",
        )
    return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


async def _validate_and_price_items(restaurant_id: int, items: List[OrderItem]):
    db = get_db()
    rest = await db.restaurants.find_one({"id": restaurant_id})
    if not rest:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    if not rest["is_open"]:
        raise HTTPException(status_code=400, detail="Restaurant is currently closed")

    total = 0.0
    order_items_data = []
    for item in items:
        if item.quantity <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be at least 1")
        menu_item = await db.menu_items.find_one({"id": item.item_id})
        if not menu_item:
            raise HTTPException(status_code=404, detail=f"Item {item.item_id} not found")
        if menu_item["restaurant_id"] != restaurant_id:
            raise HTTPException(
                status_code=400,
                detail=f"Item {menu_item['name']} does not belong to this restaurant",
            )
        if not menu_item["is_available"]:
            raise HTTPException(
                status_code=400,
                detail=f"Item {menu_item['name']} is currently unavailable",
            )

        item_total = float(menu_item["price"]) * item.quantity
        total += item_total
        order_items_data.append(
            {
                "item_id": menu_item["id"],
                "item_name": menu_item["name"],
                "quantity": item.quantity,
                "price": float(menu_item["price"]),
            }
        )

    amount_paise = int(round(total * 100))
    if amount_paise <= 0:
        raise HTTPException(status_code=400, detail="Order amount must be greater than zero")

    return order_items_data, total, amount_paise


@router.post("/payments/create-order")
async def create_payment_order(payload: CreatePaymentOrderRequest, authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    user_id = await get_user_from_token(token)
    db = get_db()

    order_items_data, total, amount_paise = await _validate_and_price_items(
        payload.restaurant_id, payload.items
    )

    receipt = f"ezf_{user_id}_{random.randint(10000, 99999)}"
    client = _rzp_client()
    try:
        razorpay_order = client.order.create(
            {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": receipt,
                "notes": {
                    "user_id": str(user_id),
                    "restaurant_id": str(payload.restaurant_id),
                },
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Razorpay order creation failed: {exc}") from exc

    await db.payment_intents.update_one(
        {"razorpay_order_id": razorpay_order["id"]},
        {
            "$set": {
                "razorpay_order_id": razorpay_order["id"],
                "user_id": user_id,
                "restaurant_id": payload.restaurant_id,
                "items": order_items_data,
                "total": total,
                "amount_paise": amount_paise,
                "currency": "INR",
                "status": "created",
                "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
        },
        upsert=True,
    )

    return {
        "key_id": RAZORPAY_KEY_ID,
        "razorpay_order_id": razorpay_order["id"],
        "amount": amount_paise,
        "currency": "INR",
        "total": total,
        "restaurant_id": payload.restaurant_id,
    }


@router.post("/payments/verify-and-place-order")
async def verify_and_place_order(payload: VerifyAndPlaceOrderRequest, authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    user_id = await get_user_from_token(token)
    db = get_db()

    intent = await db.payment_intents.find_one(
        {"razorpay_order_id": payload.razorpay_order_id, "user_id": user_id}
    )
    if not intent:
        raise HTTPException(status_code=404, detail="Payment intent not found")

    existing_order = await db.orders.find_one(
        {"payment_id": payload.razorpay_payment_id}, {"_id": 0}
    )
    if existing_order:
        return {
            "order_id": existing_order["id"],
            "secret_code": existing_order["secret_code"],
            "total": existing_order["total"],
            "status": existing_order["status"],
        }

    client = _rzp_client()
    signature_payload = {
        "razorpay_order_id": payload.razorpay_order_id,
        "razorpay_payment_id": payload.razorpay_payment_id,
        "razorpay_signature": payload.razorpay_signature,
    }
    try:
        client.utility.verify_payment_signature(signature_payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Payment signature verification failed")

    order_id = await get_next_id("orders")
    secret_code = f"#{random.randint(1000, 9999)}"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    await db.orders.insert_one(
        {
            "id": order_id,
            "user_id": user_id,
            "restaurant_id": intent["restaurant_id"],
            "secret_code": secret_code,
            "status": "preparing",
            "total": intent["total"],
            "items": intent["items"],
            "created_at": now,
            "payment_status": "paid",
            "payment_id": payload.razorpay_payment_id,
            "razorpay_order_id": payload.razorpay_order_id,
            "payment_verified_at": now,
            "user_acknowledged": False,
        }
    )

    await db.payment_intents.update_one(
        {"razorpay_order_id": payload.razorpay_order_id},
        {
            "$set": {
                "status": "paid",
                "payment_id": payload.razorpay_payment_id,
                "razorpay_signature": payload.razorpay_signature,
                "verified_at": now,
                "order_id": order_id,
            }
        },
    )

    return {
        "order_id": order_id,
        "secret_code": secret_code,
        "total": intent["total"],
        "status": "preparing",
    }
