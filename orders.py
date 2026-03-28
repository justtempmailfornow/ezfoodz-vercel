from fastapi import APIRouter, HTTPException, Header, Body
from database import get_db, get_next_id
from restaurant_auth import get_restaurant_from_token
import random
from pydantic import BaseModel
from typing import List
from datetime import datetime, timezone
from transaction_logger import log_completed_order

router = APIRouter(tags=["Orders"])


class OrderItem(BaseModel):
    item_id: int
    quantity: int


class PlaceOrderRequest(BaseModel):
    restaurant_id: int
    items: List[OrderItem]


async def get_user_from_token(token: str):
    db = get_db()
    session = await db.user_sessions.find_one({"token": token})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid token")
    return session["user_id"]


@router.post("/orders")
async def place_order(order: PlaceOrderRequest, authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    user_id = await get_user_from_token(token)

    db = get_db()

    # Check restaurant is open
    rest = await db.restaurants.find_one({"id": order.restaurant_id})
    if not rest:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    if not rest["is_open"]:
        raise HTTPException(status_code=400, detail="Restaurant is currently closed")

    # Generate secret code
    secret_code = f"#{random.randint(1000, 9999)}"

    # Calculate total and validate items
    total = 0.0
    order_items_data = []
    for item in order.items:
        menu_item = await db.menu_items.find_one({"id": item.item_id})
        if not menu_item:
            raise HTTPException(status_code=404, detail=f"Item {item.item_id} not found")
        if menu_item["restaurant_id"] != order.restaurant_id:
            raise HTTPException(status_code=400, detail=f"Item {menu_item['name']} does not belong to this restaurant")
        if not menu_item["is_available"]:
            raise HTTPException(status_code=400, detail=f"Item {menu_item['name']} is currently unavailable")

        item_total = menu_item["price"] * item.quantity
        total += item_total
        order_items_data.append({
            "item_id": menu_item["id"],
            "item_name": menu_item["name"],
            "quantity": item.quantity,
            "price": menu_item["price"],
        })

    # Create order
    order_id = await get_next_id("orders")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    await db.orders.insert_one({
        "id": order_id,
        "user_id": user_id,
        "restaurant_id": order.restaurant_id,
        "secret_code": secret_code,
        "status": "preparing",
        "total": total,
        "items": order_items_data,
        "created_at": now,
    })

    return {
        "order_id": order_id,
        "secret_code": secret_code,
        "total": total,
        "status": "preparing"
    }


@router.get("/orders/user/active")
async def get_user_active_orders(authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    user_id = await get_user_from_token(token)

    db = get_db()
    cursor = db.orders.find(
        {
            "user_id": user_id,
            "$or": [
                {"status": {"$ne": "given"}},
                {"status": "given", "user_acknowledged": False},
            ],
        },
        {"_id": 0}
    ).sort("created_at", -1)

    orders = []
    async for order in cursor:
        # Add restaurant name
        rest = await db.restaurants.find_one({"id": order["restaurant_id"]}, {"name": 1})
        order["restaurant_name"] = rest["name"] if rest else ""
        orders.append(order)

    return {"orders": orders}


@router.get("/orders/user/history")
async def get_user_order_history(authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    user_id = await get_user_from_token(token)

    db = get_db()
    cursor = db.orders.find(
        {
            "user_id": user_id,
            "status": "given",
            "$or": [{"user_acknowledged": True}, {"user_acknowledged": {"$exists": False}}],
        },
        {"_id": 0}
    ).sort("created_at", -1).limit(50)

    orders = []
    async for order in cursor:
        rest = await db.restaurants.find_one({"id": order["restaurant_id"]}, {"name": 1})
        order["restaurant_name"] = rest["name"] if rest else ""
        orders.append(order)

    return {"orders": orders}


@router.get("/orders/restaurant/{restaurant_id}")
async def get_restaurant_orders(restaurant_id: int, authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    rid = await get_restaurant_from_token(token)
    if rid != restaurant_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    db = get_db()
    cursor = db.orders.find(
        {"restaurant_id": restaurant_id, "status": {"$ne": "given"}},
        {"_id": 0}
    ).sort("created_at", 1)

    orders = await cursor.to_list(length=500)
    return {"orders": orders}


@router.get("/orders/restaurant/{restaurant_id}/history")
async def get_restaurant_order_history(restaurant_id: int, authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    rid = await get_restaurant_from_token(token)
    if rid != restaurant_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    db = get_db()
    cursor = db.orders.find(
        {"restaurant_id": restaurant_id, "status": "given"},
        {"_id": 0}
    ).sort("created_at", -1).limit(100)

    orders = await cursor.to_list(length=100)
    return {"orders": orders}


@router.put("/orders/{order_id}/status")
async def update_order_status(order_id: int, authorization: str = Header(...), status: str = Body(..., embed=True)):
    token = authorization.replace("Bearer ", "")

    valid_statuses = ["preparing", "ready", "given"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    db = get_db()
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    rid = await get_restaurant_from_token(token)
    if rid != order["restaurant_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Enforce status flow
    status_flow = {"preparing": "ready", "ready": "given"}
    current = order["status"]
    if current in status_flow and status != status_flow[current]:
        raise HTTPException(status_code=400, detail=f"Cannot change from '{current}' to '{status}'. Next status should be '{status_flow[current]}'")

    await db.orders.update_one({"id": order_id}, {"$set": {"status": status}})

    if status == "given":
        updated_order = await db.orders.find_one({"id": order_id}, {"_id": 0})
        if updated_order:
            await log_completed_order(updated_order)

    return {"status": status}


@router.post("/orders/{order_id}/acknowledge")
async def acknowledge_order(order_id: int, authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    user_id = await get_user_from_token(token)

    db = get_db()
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if order["status"] != "given":
        raise HTTPException(status_code=400, detail="Order is not delivered yet")

    await db.orders.update_one(
        {"id": order_id},
        {
            "$set": {
                "user_acknowledged": True,
                "acknowledged_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
        },
    )

    return {"status": "acknowledged"}
