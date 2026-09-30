# mjueyesu_api.py
# Seva ndogo ya kuhifadhi maudhui ya siku za MJUE YESU (huru kabisa na NjiaMauzo).
# Weka faili hii kwenye mzizi wa repo yako (karibu na app.py), kisha ongeza
# mistari miwili hii ndani ya app.py (karibu na sehemu ya "app = Flask(...)"):
#
#     from mjueyesu_api import mjueyesu_bp
#     app.register_blueprint(mjueyesu_bp)
#
# Data zinahifadhiwa kwenye faili la SQLite (mjueyesu.db) kwenye seva —
# haziko tena ndani ya simu, hivyo kufomati simu hakuziondoi.
#
# MUHIMU (Render free tier): diski ya "Web Service" ya bure HAIDUMU wakati
# wa "redeploy" mpya (inafutika ikiwa umebofya deploy tena au umebadilisha
# kanuni). Kwa ulinzi wa kudumu zaidi, baadaye unaweza kuhamishia data hii
# kwenye Render Postgres (bure kwa miezi michache) badala ya SQLite — nitakusaidia
# ukiomba. Kwa sasa, epuka "Manual Deploy" isiyo ya lazima ili usipoteze data.

import os
import re
import sqlite3
import time
import json
import base64
from flask import Blueprint, request, jsonify, g, Response

mjueyesu_bp = Blueprint("mjueyesu_api", __name__, url_prefix="/api/mjueyesu")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mjueyesu.db")
ADMIN_USER = os.environ.get("MJUEYESU_ADMIN_USER", "Mjue Yesu")
ADMIN_PASS = os.environ.get("MJUEYESU_ADMIN_PASS", "njiazote")


def get_db():
    db = getattr(g, "_mjueyesu_db", None)
    if db is None:
        db = g._mjueyesu_db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS entries(
        id TEXT PRIMARY KEY, lesson TEXT, day TEXT, title TEXT,
        text TEXT, hide INTEGER, updated TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS titles(
        lesson TEXT PRIMARY KEY, title TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS images(
        id TEXT PRIMARY KEY, mime TEXT, data BLOB)""")
    conn.commit()
    conn.close()


init_db()


@mjueyesu_bp.teardown_app_request
def _close_db(exc):
    db = getattr(g, "_mjueyesu_db", None)
    if db is not None:
        db.close()


@mjueyesu_bp.after_request
def _cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Admin-User, X-Admin-Pass"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp


def _authed():
    return (request.headers.get("X-Admin-User") == ADMIN_USER and
            request.headers.get("X-Admin-Pass") == ADMIN_PASS)


@mjueyesu_bp.route("/data", methods=["GET", "OPTIONS"])
def get_data():
    if request.method == "OPTIONS":
        return ("", 204)
    db = get_db()
    entries = [dict(r) for r in db.execute("SELECT * FROM entries")]
    for e in entries:
        e["hide"] = bool(e["hide"])
    titles = {r["lesson"]: r["title"] for r in db.execute("SELECT * FROM titles")}
    return jsonify({"entries": entries, "titles": titles, "server_time": time.time()})


@mjueyesu_bp.route("/login", methods=["POST", "OPTIONS"])
def login():
    if request.method == "OPTIONS":
        return ("", 204)
    d = request.get_json(silent=True) or {}
    if d.get("user") == ADMIN_USER and d.get("pass") == ADMIN_PASS:
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 401


@mjueyesu_bp.route("/save", methods=["POST", "OPTIONS"])
def save_entry():
    if request.method == "OPTIONS":
        return ("", 204)
    if not _authed():
        return jsonify({"ok": False, "error": "auth"}), 401
    e = request.get_json(silent=True) or {}
    if not e.get("id") or not e.get("lesson") or not e.get("day"):
        return jsonify({"ok": False, "error": "data"}), 400
    db = get_db()
    db.execute("""INSERT INTO entries(id,lesson,day,title,text,hide,updated)
                  VALUES(?,?,?,?,?,?,?)
                  ON CONFLICT(id) DO UPDATE SET
                  lesson=excluded.lesson, day=excluded.day, title=excluded.title,
                  text=excluded.text, hide=excluded.hide, updated=excluded.updated""",
               (e["id"], e["lesson"], e["day"], e.get("title", ""),
                e.get("text", ""), 1 if e.get("hide") else 0,
                e.get("updated") or ""))
    db.commit()
    return jsonify({"ok": True})


@mjueyesu_bp.route("/delete", methods=["POST", "OPTIONS"])
def delete_entry():
    if request.method == "OPTIONS":
        return ("", 204)
    if not _authed():
        return jsonify({"ok": False, "error": "auth"}), 401
    d = request.get_json(silent=True) or {}
    if not d.get("id"):
        return jsonify({"ok": False, "error": "id"}), 400
    db = get_db()
    db.execute("DELETE FROM entries WHERE id=?", (d["id"],))
    db.commit()
    return jsonify({"ok": True})


@mjueyesu_bp.route("/title", methods=["POST", "OPTIONS"])
def set_title():
    if request.method == "OPTIONS":
        return ("", 204)
    if not _authed():
        return jsonify({"ok": False, "error": "auth"}), 401
    d = request.get_json(silent=True) or {}
    if not d.get("lesson"):
        return jsonify({"ok": False, "error": "lesson"}), 400
    db = get_db()
    if d.get("title"):
        db.execute("""INSERT INTO titles(lesson,title) VALUES(?,?)
                      ON CONFLICT(lesson) DO UPDATE SET title=excluded.title""",
                   (d["lesson"], d["title"]))
    else:
        db.execute("DELETE FROM titles WHERE lesson=?", (d["lesson"],))
    db.commit()
    return jsonify({"ok": True})


# ---------- Picha za ukurasa (SEVA_PICHA_ROUTES.md) ----------
_DATA_URL_RE = re.compile(r"^data:(image/jpeg|image/png|image/webp);base64,(.+)$", re.S)
IMAGE_MAX_BYTES = 3 * 1024 * 1024  # 3MB baada ya kuondoa base64


@mjueyesu_bp.route("/image", methods=["POST", "OPTIONS"])
def save_image():
    if request.method == "OPTIONS":
        return ("", 204)
    if not _authed():
        return jsonify({"ok": False, "error": "auth"}), 401
    d = request.get_json(silent=True) or {}
    img_id = str(d.get("id") or "").strip()
    m = _DATA_URL_RE.match(d.get("data") or "")
    if not img_id or not m:
        return jsonify({"ok": False, "error": "data"}), 400
    try:
        raw = base64.b64decode(m.group(2))
    except Exception:
        return jsonify({"ok": False, "error": "base64"}), 400
    if len(raw) > IMAGE_MAX_BYTES:
        return jsonify({"ok": False, "error": "too_large"}), 413
    db = get_db()
    db.execute("""INSERT INTO images(id,mime,data) VALUES(?,?,?)
                  ON CONFLICT(id) DO UPDATE SET mime=excluded.mime, data=excluded.data""",
               (img_id, m.group(1), raw))
    db.commit()
    return jsonify({"ok": True})


@mjueyesu_bp.route("/image/<path:img_id>", methods=["GET", "OPTIONS"])
def get_image(img_id):
    if request.method == "OPTIONS":
        return ("", 204)
    db = get_db()
    row = db.execute("SELECT mime, data FROM images WHERE id=?", (img_id,)).fetchone()
    if not row:
        return ("", 404)
    resp = Response(row["data"], mimetype=row["mime"])
    resp.headers["Cache-Control"] = "public, max-age=604800"
    return resp


@mjueyesu_bp.route("/image/delete", methods=["POST", "OPTIONS"])
def delete_image():
    if request.method == "OPTIONS":
        return ("", 204)
    if not _authed():
        return jsonify({"ok": False, "error": "auth"}), 401
    d = request.get_json(silent=True) or {}
    img_id = str(d.get("id") or "").strip()
    if not img_id:
        return jsonify({"ok": False, "error": "id"}), 400
    db = get_db()
    db.execute("DELETE FROM images WHERE id=?", (img_id,))
    db.commit()
    return jsonify({"ok": True})
