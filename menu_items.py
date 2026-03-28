from fastapi import APIRouter, Form, HTTPException, Header
from database import get_db, get_next_id
from restaurant_auth import get_restaurant_from_token

router = APIRouter(tags=["Menu Items"])


@router.get("/menu/{restaurant_id}")
async def get_menu(restaurant_id: int, all: bool = False):
    """Get menu items for a restaurant. If all=False (default), only available items."""
    db = get_db()

    query = {"restaurant_id": restaurant_id}
    if not all:
        query["is_available"] = True

    cursor = db.menu_items.find(query, {"_id": 0})
    items = await cursor.to_list(length=500)
    return {"items": items}


@router.post("/menu/{restaurant_id}")
async def add_item(
    restaurant_id: int,
    authorization: str = Header(...),
    name: str = Form(...),
    category: str = Form("veg"),
    cuisine: str = Form(""),
    price: float = Form(...)
):
    token = authorization.replace("Bearer ", "")
    rid = await get_restaurant_from_token(token)
    if rid != restaurant_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    db = get_db()
    item_id = await get_next_id("menu_items")

    item = {
        "id": item_id,
        "restaurant_id": restaurant_id,
        "name": name,
        "category": category,
        "cuisine": cuisine,
        "price": price,
        "is_available": True,
    }
    await db.menu_items.insert_one(item)

    return {"id": item_id, "name": name, "category": category, "cuisine": cuisine, "price": price, "is_available": True}


@router.put("/menu/item/{item_id}")
async def edit_item(
    item_id: int,
    authorization: str = Header(...),
    name: str = Form(""),
    category: str = Form(""),
    cuisine: str = Form(""),
    price: float = Form(0)
):
    token = authorization.replace("Bearer ", "")
    db = get_db()

    item = await db.menu_items.find_one({"id": item_id})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    rid = await get_restaurant_from_token(token)
    if rid != item["restaurant_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    updates = {}
    if name:
        updates["name"] = name
    if category:
        updates["category"] = category
    if cuisine:
        updates["cuisine"] = cuisine
    if price > 0:
        updates["price"] = price

    if updates:
        await db.menu_items.update_one({"id": item_id}, {"$set": updates})

    return {"status": "updated"}


@router.delete("/menu/item/{item_id}")
async def delete_item(item_id: int, authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    db = get_db()

    item = await db.menu_items.find_one({"id": item_id})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    rid = await get_restaurant_from_token(token)
    if rid != item["restaurant_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    await db.menu_items.delete_one({"id": item_id})
    return {"status": "deleted"}


@router.put("/menu/item/{item_id}/toggle")
async def toggle_item(item_id: int, authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    db = get_db()

    item = await db.menu_items.find_one({"id": item_id})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    rid = await get_restaurant_from_token(token)
    if rid != item["restaurant_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    new_status = not item["is_available"]
    await db.menu_items.update_one({"id": item_id}, {"$set": {"is_available": new_status}})

    return {"is_available": new_status}
