from fastapi import APIRouter, Form, HTTPException, Header
from database import get_db
from Databases.hashing import verify_password
import uuid

router = APIRouter(tags=["Restaurant Auth"])


@router.post("/restaurant/login")
async def restaurant_login(email: str = Form(...), password: str = Form(...)):
    db = get_db()

    rest = await db.restaurants.find_one({"email": email})
    if not rest or not verify_password(password, rest["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = str(uuid.uuid4())
    await db.restaurant_sessions.insert_one({"token": token, "restaurant_id": rest["id"]})

    return {"token": token, "restaurant_id": rest["id"], "name": rest["name"]}


async def get_restaurant_from_token(token: str):
    """Helper to validate restaurant session token and return restaurant_id."""
    db = get_db()
    session = await db.restaurant_sessions.find_one({"token": token})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session token")
    return session["restaurant_id"]


@router.get("/restaurant/me")
async def restaurant_me(authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    rid = await get_restaurant_from_token(token)

    db = get_db()
    rest = await db.restaurants.find_one(
        {"id": rid},
        {"_id": 0, "password": 0}
    )
    if not rest:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    return rest
