"""Database initialization and seeding for MongoDB."""
import asyncio
import os
from database import connect_db, close_db, get_db, get_next_id
from Databases.hashing import hash_password


async def init_db():
    """Initialize the database with seed data if empty."""
    db = get_db()

    # Check if restaurants already seeded
    count = await db.restaurants.count_documents({})
    if count > 0:
        print("✅ Database already initialized")
        return

    print("🌱 Seeding database...")
    os.makedirs("uploads", exist_ok=True)

    # Seed restaurants
    seed_restaurants = [
        {
            "name": "Rishabs FoodCourt",
            "email": "rfcssn@ssncanteen.in",
            "description": "The best food court on campus",
            "cuisine_type": "Multi-Cuisine",
            "address": "Main Block, Ground Floor",
            "phone": "9876543210",
            "password": hash_password("rfcssn@ezfoodz"),
            "image_path": "",
            "is_open": True,
            "rating": 4.2,
        },
        {
            "name": "Main Canteen",
            "email": "mcssn@ssncanteen.in",
            "description": "The main campus canteen with a wide variety of meals",
            "cuisine_type": "Indian",
            "address": "Main Block, First Floor",
            "phone": "9876543211",
            "password": hash_password("mcssn@ezfoodz"),
            "image_path": "",
            "is_open": True,
            "rating": 4.5,
        },
        {
            "name": "Ashwins FoodCourt",
            "email": "afcssn@ssncanteen.in",
            "description": "Delicious food and snacks",
            "cuisine_type": "South Indian",
            "address": "South Block, Ground Floor",
            "phone": "9876543212",
            "password": hash_password("afcssn@ezfoodz"),
            "image_path": "",
            "is_open": True,
            "rating": 4.0,
        },
        {
            "name": "Snow Cube",
            "email": "scssn@ssncanteen.in",
            "description": "Cool drinks, shakes and frozen treats",
            "cuisine_type": "Beverages",
            "address": "Near Library",
            "phone": "9876543213",
            "password": hash_password("scssn@ezfoodz"),
            "image_path": "",
            "is_open": True,
            "rating": 4.6,
        },
    ]

    for rest in seed_restaurants:
        rest["id"] = await get_next_id("restaurants")
        await db.restaurants.insert_one(rest)

    # Seed menu items
    items = [
        (1, "Chicken Biryani", "non-veg", "Indian", 120),
        (1, "Veg Biryani", "veg", "Indian", 90),
        (1, "Chicken Fried Rice", "non-veg", "Chinese", 100),
        (1, "Paneer Butter Masala", "veg", "Indian", 110),
        (1, "Chapati (2 pcs)", "veg", "Indian", 30),
        (1, "Notebook", "stationary", "", 40),
        (2, "Masala Dosa", "veg", "South Indian", 50),
        (2, "Idli (3 pcs)", "veg", "South Indian", 30),
        (2, "Chicken Samosa", "non-veg", "South Indian", 25),
        (2, "Filter Coffee", "veg", "Beverages", 20),
        (2, "Vada (2 pcs)", "veg", "South Indian", 25),
        (3, "Maggi", "veg", "Quick Bites", 30),
        (3, "Egg Maggi", "non-veg", "Quick Bites", 40),
        (3, "Bread Omelette", "non-veg", "Quick Bites", 35),
        (3, "Tea", "veg", "Beverages", 10),
        (3, "Pen", "stationary", "", 10),
        (4, "Mango Juice", "veg", "Beverages", 40),
        (4, "Watermelon Juice", "veg", "Beverages", 35),
        (4, "Banana Shake", "veg", "Beverages", 50),
        (4, "Peanut Butter Sandwich", "veg", "Quick Bites", 45),
    ]

    for restaurant_id, name, category, cuisine, price in items:
        item_id = await get_next_id("menu_items")
        await db.menu_items.insert_one({
            "id": item_id,
            "restaurant_id": restaurant_id,
            "name": name,
            "category": category,
            "cuisine": cuisine,
            "price": price,
            "is_available": True,
        })

    print("✅ Database initialized with seed data")


async def main():
    await connect_db()
    await init_db()
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
