from fastapi import APIRouter, Form, HTTPException, Header
from database import get_db, get_next_id
from Databases.hashing import hash_password, verify_password
import uuid

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register")
async def register(email: str = Form(...), password: str = Form(...), username: str = Form("")):
    db = get_db()

    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = hash_password(password)
    user_id = await get_next_id("users")

    await db.users.insert_one({
        "id": user_id,
        "email": email,
        "username": username,
        "password": hashed,
        "address": "",
        "auth_provider": "email",
        "firebase_uid": None,
    })

    token = str(uuid.uuid4())
    await db.user_sessions.insert_one({"token": token, "user_id": user_id})

    return {"user_id": user_id, "token": token, "username": username, "email": email}


@router.post("/login")
async def login(email: str = Form(...), password: str = Form(...)):
    db = get_db()

    user = await db.users.find_one({"email": email, "auth_provider": "email"})
    if not user or not verify_password(password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = str(uuid.uuid4())
    await db.user_sessions.insert_one({"token": token, "user_id": user["id"]})

    return {"user_id": user["id"], "token": token, "username": user["username"], "email": email}


@router.post("/google")
async def google_auth(email: str = Form(...), firebase_uid: str = Form(...), username: str = Form("")):
    db = get_db()

    user = await db.users.find_one({"firebase_uid": firebase_uid})

    if user:
        user_id = user["id"]
        uname = user["username"]
    else:
        # Check if email exists with different provider
        existing = await db.users.find_one({"email": email, "auth_provider": "email"})
        if existing:
            # Link accounts
            await db.users.update_one(
                {"id": existing["id"]},
                {"$set": {"firebase_uid": firebase_uid, "auth_provider": "google"}}
            )
            user_id = existing["id"]
            uname = username
        else:
            user_id = await get_next_id("users")
            await db.users.insert_one({
                "id": user_id,
                "firebase_uid": firebase_uid,
                "email": email,
                "username": username,
                "password": "",
                "address": "",
                "auth_provider": "google",
            })
            uname = username

    token = str(uuid.uuid4())
    await db.user_sessions.insert_one({"token": token, "user_id": user_id})

    return {"user_id": user_id, "token": token, "username": uname, "email": email}


@router.get("/me")
async def get_me(authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    db = get_db()

    session = await db.user_sessions.find_one({"token": token})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = await db.users.find_one({"id": session["user_id"]}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    return user
