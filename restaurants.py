from fastapi import APIRouter, Form, HTTPException, Header, UploadFile, File
from fastapi.responses import StreamingResponse
from database import get_db
from restaurant_auth import get_restaurant_from_token
from datetime import datetime
import csv
import io
import os

router = APIRouter(tags=["Restaurants"])


@router.get("/restaurants")
async def list_restaurants():
    db = get_db()
    cursor = db.restaurants.find({}, {"_id": 0, "password": 0})
    restaurants = []
    async for r in cursor:
        if r.get("image_path"):
            r["image_url"] = f"/uploads/{r['image_path']}"
        else:
            r["image_url"] = ""
        restaurants.append(r)

    return {"restaurants": restaurants}


@router.get("/restaurants/{restaurant_id}")
async def get_restaurant(restaurant_id: int):
    db = get_db()
    rest = await db.restaurants.find_one({"id": restaurant_id}, {"_id": 0, "password": 0})
    if not rest:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    rest["image_url"] = f"/uploads/{rest['image_path']}" if rest.get("image_path") else ""
    return rest


@router.put("/restaurants/{restaurant_id}")
async def update_restaurant(
    restaurant_id: int,
    authorization: str = Header(...),
    name: str = Form(""),
    description: str = Form(""),
    cuisine_type: str = Form(""),
    address: str = Form(""),
    phone: str = Form("")
):
    token = authorization.replace("Bearer ", "")
    rid = await get_restaurant_from_token(token)
    if rid != restaurant_id:
        raise HTTPException(status_code=403, detail="Not authorized for this restaurant")

    updates = {}
    if name:
        updates["name"] = name
    if description:
        updates["description"] = description
    if cuisine_type:
        updates["cuisine_type"] = cuisine_type
    if address:
        updates["address"] = address
    if phone:
        updates["phone"] = phone

    if updates:
        db = get_db()
        await db.restaurants.update_one({"id": restaurant_id}, {"$set": updates})

    return {"status": "updated"}


@router.put("/restaurants/{restaurant_id}/toggle")
async def toggle_restaurant(restaurant_id: int, authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    rid = await get_restaurant_from_token(token)
    if rid != restaurant_id:
        raise HTTPException(status_code=403, detail="Not authorized for this restaurant")

    db = get_db()
    rest = await db.restaurants.find_one({"id": restaurant_id})
    if not rest:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    new_status = not rest["is_open"]
    await db.restaurants.update_one({"id": restaurant_id}, {"$set": {"is_open": new_status}})

    return {"is_open": new_status}


@router.post("/restaurants/{restaurant_id}/image")
async def upload_restaurant_image(
    restaurant_id: int,
    authorization: str = Header(...),
    file: UploadFile = File(...)
):
    token = authorization.replace("Bearer ", "")
    rid = await get_restaurant_from_token(token)
    if rid != restaurant_id:
        raise HTTPException(status_code=403, detail="Not authorized for this restaurant")

    os.makedirs("uploads", exist_ok=True)
    ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
    filename = f"restaurant_{restaurant_id}{ext}"
    filepath = os.path.join("uploads", filename)

    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    db = get_db()
    await db.restaurants.update_one({"id": restaurant_id}, {"$set": {"image_path": filename}})

    return {"status": "uploaded", "image_url": f"/uploads/{filename}"}


@router.get("/restaurants/{restaurant_id}/export/monthly")
async def export_monthly_transactions(
    restaurant_id: int,
    month: str = "",
    authorization: str = Header(...),
):
    token = authorization.replace("Bearer ", "")
    rid = await get_restaurant_from_token(token)
    if rid != restaurant_id:
        raise HTTPException(status_code=403, detail="Not authorized for this restaurant")

    query_month = month or datetime.now().strftime("%Y-%m")

    db = get_db()
    logs = await db.monthly_logs.find(
        {"restaurant_id": restaurant_id, "month": query_month},
        {"_id": 0},
    ).sort("completed_at", -1).to_list(length=100000)

    output = io.StringIO()
    fieldnames = [
        "id",
        "order_id",
        "restaurant_id",
        "user_id",
        "gross_amount",
        "payment_id",
        "completed_at",
        "month",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for log in logs:
        writer.writerow(
            {
                "id": log.get("id", ""),
                "order_id": log.get("order_id", ""),
                "restaurant_id": log.get("restaurant_id", ""),
                "user_id": log.get("user_id", ""),
                "gross_amount": log.get("gross_amount", ""),
                "payment_id": log.get("payment_id", ""),
                "completed_at": log.get("completed_at", ""),
                "month": log.get("month", ""),
            }
        )

    filename = f"transactions_restaurant_{restaurant_id}_{query_month}.csv"
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )