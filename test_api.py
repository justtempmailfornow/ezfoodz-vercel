"""End-to-end API smoke test for EZFOODZ backend (MongoDB version)."""
import requests
import json

BASE = "http://127.0.0.1:8000"
passed = 0


def test(name, fn):
    global passed
    try:
        fn()
        print(f"  PASS: {name}")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {name} -> {e}")


def t1():
    r = requests.get(f"{BASE}/restaurants")
    assert r.status_code == 200
    data = r.json()
    assert len(data["restaurants"]) == 4
    for rest in data["restaurants"]:
        print(f"       {rest['name']} (ID={rest['id']}, open={rest['is_open']})")


def t2():
    r = requests.get(f"{BASE}/menu/1")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) > 0
    for item in items:
        print(f"       {item['name']} Rs{item['price']} ({item['category']})")


def t3():
    r = requests.post(f"{BASE}/auth/register", data={"email": "smoke@test.com", "password": "test123", "username": "smoketest"})
    assert r.status_code == 200
    data = r.json()
    assert data["token"]
    assert data["username"] == "smoketest"
    return data["token"]


def t4():
    r = requests.post(f"{BASE}/auth/login", data={"email": "smoke@test.com", "password": "test123"})
    assert r.status_code == 200
    return r.json()["token"]


def t5(token):
    r = requests.post(f"{BASE}/orders",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        data=json.dumps({"restaurant_id": 1, "items": [{"item_id": 1, "quantity": 2}, {"item_id": 2, "quantity": 1}]}))
    assert r.status_code == 200
    data = r.json()
    assert data["order_id"]
    assert data["secret_code"]
    print(f"       Order #{data['order_id']}, Code={data['secret_code']}, Total=Rs{data['total']}")
    return data["order_id"]


def t6(token):
    r = requests.get(f"{BASE}/orders/user/active", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    orders = r.json()["orders"]
    assert len(orders) > 0
    o = orders[0]
    print(f"       Code={o['secret_code']}, Status={o['status']}, Items={len(o['items'])}")


def t7():
    r = requests.post(f"{BASE}/restaurant/login", data={"email": "rfcssn@ssncanteen.in", "password": "rfcssn@ezfoodz"})
    assert r.status_code == 200
    data = r.json()
    assert data["name"]
    print(f"       Logged in as: {data['name']}")
    return data["token"]


def t8(rest_token):
    r = requests.get(f"{BASE}/restaurant/me", headers={"Authorization": f"Bearer {rest_token}"})
    assert r.status_code == 200
    data = r.json()
    print(f"       Name={data['name']}, Open={data['is_open']}")


def t9(rest_token, order_id):
    r = requests.put(f"{BASE}/orders/{order_id}/status",
        headers={"Authorization": f"Bearer {rest_token}", "Content-Type": "application/json"},
        data=json.dumps({"status": "ready"}))
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def t10(rest_token, order_id):
    r = requests.put(f"{BASE}/orders/{order_id}/status",
        headers={"Authorization": f"Bearer {rest_token}", "Content-Type": "application/json"},
        data=json.dumps({"status": "given"}))
    assert r.status_code == 200
    assert r.json()["status"] == "given"


def t11(token):
    r = requests.get(f"{BASE}/orders/user/history", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    orders = r.json()["orders"]
    assert len(orders) > 0
    print(f"       History has {len(orders)} order(s)")


def t12():
    r = requests.get(f"{BASE}/")
    assert r.status_code == 200
    data = r.json()
    assert data["database"] == "MongoDB"
    print(f"       Backend: {data['status']}, DB: {data['database']}")


if __name__ == "__main__":
    print("\n EZFOODZ API Smoke Tests (MongoDB)\n" + "=" * 40)

    test("1. List restaurants", t1)
    test("2. Get menu for restaurant 1", t2)

    user_token = None
    def _t3():
        global user_token
        user_token = t3()
    test("3. Register new user", _t3)

    def _t4():
        global user_token
        user_token = t4()
    test("4. Login with email/password", _t4)

    order_id = None
    def _t5():
        global order_id
        order_id = t5(user_token)
    test("5. Place order", _t5)

    test("6. Get active orders", lambda: t6(user_token))

    rest_token = None
    def _t7():
        global rest_token
        rest_token = t7()
    test("7. Restaurant login", _t7)

    test("8. Restaurant /me endpoint", lambda: t8(rest_token))
    test("9. Update order -> ready", lambda: t9(rest_token, order_id))
    test("10. Update order -> given", lambda: t10(rest_token, order_id))
    test("11. User order history", lambda: t11(user_token))
    test("12. Backend health check", t12)

    print(f"\n{'=' * 40}")
    print(f" Results: {passed}/12 tests passed")
    if passed == 12:
        print(" ALL TESTS PASSED!")
    print()
