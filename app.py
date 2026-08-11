import os
os.environ["DEMO_PAYMENT_MODE"] = "true"
os.environ["DATABASE_PATH"] = "/tmp/njiamauzo_test_v34.db"

from app import app, init_db, PAYMENT_METHODS

init_db()
c = app.test_client()

assert c.get("/").status_code == 200
assert c.get("/api/stats").status_code == 200

fee = c.get("/api/service/fee?country=Kenya").get_json()
assert fee["currency"] == "KES"
assert fee["base_amount_tzs"] == 1000
assert len(fee["methods"]) == 3

methods = c.get("/api/service/methods").get_json()
assert len(methods["methods"]) == 3
assert any(m["number"] == "0755 248 789" for m in methods["methods"])
assert any(m["number"] == "0625 031 460" for m in methods["methods"])
assert any(m["number"] == "0691 925 100" for m in methods["methods"])

r = c.post("/api/service/start", json={"query": "Natafuta tani 20 za ufuta Songea", "country": "Tanzania"})
assert r.status_code == 200
data = r.get_json()
rid = data["request_id"]
assert data["amount"] == 1000
assert data["currency"] == "TZS"
assert len(data["methods"]) == 3

r = c.post("/api/service/pay", json={"request_id": rid, "phone": "0712345678", "payment_method": "mpesa"})
assert r.status_code == 200
pay = r.get_json()
assert pay["status"] == "PENDING"
assert pay["payment_method"]["number"] == "0755 248 789"
assert pay["payment_method"]["name"] == "M-Pesa / Vodacom"

r = c.post("/api/service/room", json={"request_id": rid})
assert r.status_code == 403

r = c.post("/api/service/demo-verify", json={"request_id": rid})
assert r.status_code == 200 and r.get_json()["status"] == "VERIFIED"

r = c.post("/api/service/room", json={"request_id": rid})
assert r.status_code == 200 and r.get_json()["status"] == "VERIFIED"

print("ALL TESTS PASSED")
print("Payment methods OK:", list(PAYMENT_METHODS.keys()))
