from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
from pathlib import Path
import json

BASE = Path(__file__).resolve().parent
DATA = BASE / "lessons.json"
app = Flask(__name__, static_folder=str(BASE))
CORS(app)

DEFAULT = [
    {"name":"Ujasiriamali na Biashara","category":"Biashara","desc":"Mwongozo kamili wa ujasiriamali na uendeshaji wa biashara.","source":"https://www.ifc.org/en/what-we-do/topics/small-business","price":3000},
    {"name":"Masoko ya Kidijitali","category":"Masoko","desc":"Jifunze misingi ya masoko ya kidijitali na ujenzi wa chapa.","source":"https://learndigital.withgoogle.com/digitalgarage","price":3000},
    {"name":"Usimamizi wa Fedha","category":"Fedha","desc":"Misingi ya usimamizi wa fedha kwa biashara ndogo.","source":"https://www.sba.gov/business-guide/manage-your-business/finance-your-business","price":3000},
    {"name":"Kilimo Bora","category":"Kilimo","desc":"Mbinu za kilimo kwa mavuno bora na uendelevu.","source":"https://www.fao.org/family-farming/detail/en/c/84894/","price":3000},
]

def read_lessons():
    if not DATA.exists():
        DATA.write_text(json.dumps(DEFAULT, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.loads(DATA.read_text(encoding="utf-8"))

def write_lessons(items):
    DATA.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

@app.get("/")
def home():
    return send_from_directory(BASE, "index.html")

@app.get("/admin")
def admin():
    return send_from_directory(BASE, "admin.html")

@app.get("/api/lessons")
def lessons():
    # Public API intentionally does NOT expose source links.
    public = [{k:v for k,v in x.items() if k != "source"} for x in read_lessons()]
    return jsonify(public)

@app.get("/api/admin/lessons")
def admin_lessons():
    return jsonify(read_lessons())

@app.post("/api/admin/lessons")
def add_lesson():
    data = request.get_json(force=True)
    required = ["name","category","desc","source","price"]
    if any(not data.get(k) for k in required):
        return jsonify({"error":"Taarifa zote zinahitajika"}), 400
    if not str(data["source"]).startswith(("http://","https://")):
        return jsonify({"error":"Source lazima iwe http/https"}), 400
    items = read_lessons()
    items.append(data)
    write_lessons(items)
    return jsonify(data), 201

@app.delete("/api/admin/lessons/<int:index>")
def delete_lesson(index):
    items = read_lessons()
    if index < 0 or index >= len(items):
        return jsonify({"error":"Somo halipo"}), 404
    items.pop(index)
    write_lessons(items)
    return jsonify({"ok": True})

@app.get("/health")
def health():
    return jsonify({"status":"ok","service":"NjiaMauzo Afrika"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
