from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from pathlib import Path
import json, uuid, mimetypes

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / "uploads"
LESSONS = BASE / "lessons.json"
REELS = BASE / "reels.json"
UPLOADS.mkdir(exist_ok=True)

app = Flask(__name__, static_folder=str(BASE))
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024
CORS(app)

DEFAULT_LESSONS = [
 {"name":"Ujasiriamali na Biashara","category":"Biashara","desc":"Mikakati ya kuanzisha, kukuza na kuendesha biashara kwa faida.","source":"https://www.ifc.org/en/what-we-do/topics/small-business","price":3000},
 {"name":"Masoko ya Kidijitali","category":"Masoko","desc":"Jifunze misingi ya masoko ya kidijitali na ujenzi wa chapa.","source":"https://learndigital.withgoogle.com/digitalgarage","price":3000},
 {"name":"Usimamizi wa Fedha","category":"Fedha","desc":"Misingi ya usimamizi wa fedha kwa biashara ndogo.","source":"https://www.sba.gov/business-guide/manage-your-business/finance-your-business","price":3000},
 {"name":"Kilimo Bora","category":"Kilimo","desc":"Mbinu za kilimo kwa mavuno bora na uendelevu.","source":"https://www.fao.org/family-farming/detail/en/c/84894/","price":3000}
]

def load(path, default):
    if not path.exists():
        path.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default

def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

@app.get("/")
def home(): return send_from_directory(BASE, "index.html")

@app.get("/admin")
def admin(): return send_from_directory(BASE, "admin.html")

@app.get("/uploads/<path:name>")
def uploaded(name): return send_from_directory(UPLOADS, name)

# PUBLIC: source links are deliberately removed.
@app.get("/api/lessons")
def public_lessons():
    items = load(LESSONS, DEFAULT_LESSONS)
    return jsonify([{k:v for k,v in x.items() if k != "source"} for x in items])

# ADMIN: source links remain visible here.
@app.get("/api/admin/lessons")
def admin_lessons():
    return jsonify(load(LESSONS, DEFAULT_LESSONS))

@app.post("/api/admin/lessons")
def add_lesson():
    data = request.get_json(silent=True) or {}
    required = ("name","category","source")
    if any(not str(data.get(k,"")).strip() for k in required):
        return jsonify({"error":"Jina, kategoria na chanzo vinahitajika."}),400
    source = str(data["source"]).strip()
    if not source.startswith(("http://","https://")):
        return jsonify({"error":"Chanzo lazima kiwe http:// au https://"}),400
    items = load(LESSONS, DEFAULT_LESSONS)
    item = {"name":str(data["name"]).strip(),"category":str(data["category"]).strip(),
            "desc":str(data.get("desc","")).strip(),"source":source,
            "price":int(float(data.get("price",0) or 0))}
    items.append(item); save(LESSONS, items)
    return jsonify(item),201

@app.delete("/api/admin/lessons/<int:index>")
def delete_lesson(index):
    items = load(LESSONS, DEFAULT_LESSONS)
    if index < 0 or index >= len(items): return jsonify({"error":"Somo halipo"}),404
    items.pop(index); save(LESSONS,items); return jsonify({"ok":True})

@app.get("/api/reels")
def public_reels():
    return jsonify(load(REELS, []))

@app.get("/api/admin/reels")
def admin_reels():
    return jsonify(load(REELS, []))

@app.post("/api/admin/reels")
def upload_reel():
    video = request.files.get("video")
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    if not video or not title:
        return jsonify({"error":"Jina la Reel na video vinahitajika."}),400
    allowed = {".mp4",".webm",".mov",".m4v"}
    ext = Path(video.filename or "").suffix.lower()
    if ext not in allowed:
        return jsonify({"error":"Tumia MP4, WebM, MOV au M4V."}),400
    if video.mimetype and not video.mimetype.startswith("video/"):
        return jsonify({"error":"Faili lazima iwe video."}),400
    filename = secure_filename(Path(video.filename).stem)[:50] + "_" + uuid.uuid4().hex[:10] + ext
    video.save(UPLOADS / filename)
    items = load(REELS, [])
    item = {"id":int(uuid.uuid4().int % 2147483647),"title":title,"description":description,
            "filename":filename,"url":f"/uploads/{filename}"}
    items.insert(0,item); save(REELS,items)
    return jsonify(item),201

@app.delete("/api/admin/reels/<int:reel_id>")
def delete_reel(reel_id):
    items = load(REELS, [])
    found = next((x for x in items if int(x.get("id",0)) == reel_id), None)
    if not found: return jsonify({"error":"Reel haipo"}),404
    try: (UPLOADS / found["filename"]).unlink(missing_ok=True)
    except Exception: pass
    items = [x for x in items if int(x.get("id",0)) != reel_id]
    save(REELS,items); return jsonify({"ok":True})

@app.get("/health")
def health(): return jsonify({"status":"ok","service":"NjiaMauzo Afrika"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
