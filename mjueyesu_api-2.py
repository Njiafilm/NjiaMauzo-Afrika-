# mjueyesu_api.py
# Seva ya kuhifadhi maudhui ya MJUE YESU.
#
# Hifadhi: ikiwa DATABASE_URL imewekwa (Neon/Postgres) data inahifadhiwa huko
# kwa KUDUMU. Ikiwa haijawekwa, inatumia SQLite (mjueyesu.db) kama awali
# (diski ya Render ya bure inafutika - tumia Postgres kwa data za kudumu).
#
# Kwenye app.py hakuna mabadiliko yanayohitajika (blueprint ilishasajiliwa).

import os
import re
import sqlite3
import threading
import time
import base64
import secrets
from flask import Blueprint, request, jsonify, g, Response

mjueyesu_bp = Blueprint("mjueyesu_api", __name__, url_prefix="/api/mjueyesu")

DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip()
USE_PG = bool(DATABASE_URL)
if USE_PG:
    import psycopg2
    import psycopg2.extras

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mjueyesu.db")
ADMIN_USER = os.environ.get("MJUEYESU_ADMIN_USER", "Mjue Yesu")
ADMIN_PASS = os.environ.get("MJUEYESU_ADMIN_PASS", "njiazote")


class _DB:
    """Kifuniko kidogo kinachofanya kazi na Postgres na SQLite kwa msimbo mmoja."""

    def __init__(self):
        if USE_PG:
            self.conn = psycopg2.connect(
                DATABASE_URL, connect_timeout=15,
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
        else:
            self.conn = sqlite3.connect(DB_PATH)
            self.conn.row_factory = sqlite3.Row

    def execute(self, sql, params=()):
        if USE_PG:
            cur = self.conn.cursor()
            cur.execute(sql.replace("?", "%s"), params)
            return cur
        return self.conn.execute(sql, params)

    def commit(self):
        self.conn.commit()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


def _blob(raw):
    return psycopg2.Binary(raw) if USE_PG else raw


_init_lock = threading.Lock()
_init_done = False


def _ensure_init():
    """Tengeneza majedwali mara moja. Isipofanikiwa (mfano hifadhidata iko
    usingizini), jaribu tena kwenye ombi lijalo - app haianguki."""
    global _init_done
    if _init_done:
        return
    with _init_lock:
        if _init_done:
            return
        db = _DB()
        try:
            blob_type = "BYTEA" if USE_PG else "BLOB"
            db.execute("""CREATE TABLE IF NOT EXISTS entries(
                id TEXT PRIMARY KEY, lesson TEXT, day TEXT, title TEXT,
                text TEXT, hide INTEGER, updated TEXT)""")
            db.execute("""CREATE TABLE IF NOT EXISTS titles(
                lesson TEXT PRIMARY KEY, title TEXT)""")
            db.execute(f"""CREATE TABLE IF NOT EXISTS images(
                id TEXT PRIMARY KEY, mime TEXT, data {blob_type})""")
            db.commit()
            _init_done = True
        finally:
            db.close()


def get_db():
    _ensure_init()
    db = getattr(g, "_mjueyesu_db", None)
    if db is None:
        db = g._mjueyesu_db = _DB()
    return db


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


@mjueyesu_bp.errorhandler(Exception)
def _err(e):
    # Hifadhidata ikikosekana, app ipokee kosa la wazi (itajaribu tena baadaye).
    return jsonify({"ok": False, "error": "db", "detail": str(e)[:200]}), 503


def _authed():
    u = request.headers.get("X-Admin-User") or ""
    p = request.headers.get("X-Admin-Pass") or ""
    return (secrets.compare_digest(u, ADMIN_USER) and
            secrets.compare_digest(p, ADMIN_PASS))


@mjueyesu_bp.route("/health", methods=["GET"])
def health():
    db = get_db()
    n = db.execute("SELECT COUNT(*) AS c FROM entries").fetchone()["c"]
    return jsonify({"ok": True, "backend": "postgres" if USE_PG else "sqlite",
                    "persistent": USE_PG, "entries": n})


@mjueyesu_bp.route("/data", methods=["GET", "OPTIONS"])
def get_data():
    if request.method == "OPTIONS":
        return ("", 204)
    db = get_db()
    entries = [dict(r) for r in db.execute("SELECT * FROM entries").fetchall()]
    for e in entries:
        e["hide"] = bool(e["hide"])
    titles = {r["lesson"]: r["title"] for r in db.execute("SELECT * FROM titles").fetchall()}
    return jsonify({"entries": entries, "titles": titles, "server_time": time.time()})


@mjueyesu_bp.route("/login", methods=["POST", "OPTIONS"])
def login():
    if request.method == "OPTIONS":
        return ("", 204)
    d = request.get_json(silent=True) or {}
    if (secrets.compare_digest(str(d.get("user") or ""), ADMIN_USER) and
            secrets.compare_digest(str(d.get("pass") or ""), ADMIN_PASS)):
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 401


def _upsert_entry(db, e):
    db.execute("""INSERT INTO entries(id,lesson,day,title,text,hide,updated)
                  VALUES(?,?,?,?,?,?,?)
                  ON CONFLICT(id) DO UPDATE SET
                  lesson=excluded.lesson, day=excluded.day, title=excluded.title,
                  text=excluded.text, hide=excluded.hide, updated=excluded.updated""",
               (e["id"], e["lesson"], e["day"], e.get("title", ""),
                e.get("text", ""), 1 if e.get("hide") else 0,
                e.get("updated") or ""))


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
    _upsert_entry(db, e)
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


# ---------- Nakala rudufu: export / import (admin pekee) ----------
@mjueyesu_bp.route("/export", methods=["GET", "OPTIONS"])
def export_all():
    """Pakua maudhui yote (na picha, base64) kama JSON - hifadhi faili hili."""
    if request.method == "OPTIONS":
        return ("", 204)
    if not _authed():
        return jsonify({"ok": False, "error": "auth"}), 401
    db = get_db()
    entries = [dict(r) for r in db.execute("SELECT * FROM entries").fetchall()]
    titles = {r["lesson"]: r["title"] for r in db.execute("SELECT * FROM titles").fetchall()}
    images = []
    for r in db.execute("SELECT id, mime, data FROM images").fetchall():
        images.append({"id": r["id"], "mime": r["mime"],
                       "data": base64.b64encode(bytes(r["data"])).decode()})
    return jsonify({"ok": True, "entries": entries, "titles": titles,
                    "images": images, "exported_at": time.time()})


@mjueyesu_bp.route("/import", methods=["POST", "OPTIONS"])
def import_all():
    """Rudisha maudhui kutoka kwenye faili la /export (haifuti kilichopo)."""
    if request.method == "OPTIONS":
        return ("", 204)
    if not _authed():
        return jsonify({"ok": False, "error": "auth"}), 401
    d = request.get_json(silent=True) or {}
    db = get_db()
    n = 0
    for e in d.get("entries") or []:
        if e.get("id") and e.get("lesson") and e.get("day"):
            _upsert_entry(db, e)
            n += 1
    for lesson, title in (d.get("titles") or {}).items():
        if lesson and title:
            db.execute("""INSERT INTO titles(lesson,title) VALUES(?,?)
                          ON CONFLICT(lesson) DO UPDATE SET title=excluded.title""",
                       (lesson, title))
    for im in d.get("images") or []:
        try:
            raw = base64.b64decode(im["data"])
            db.execute("""INSERT INTO images(id,mime,data) VALUES(?,?,?)
                          ON CONFLICT(id) DO UPDATE SET mime=excluded.mime, data=excluded.data""",
                       (im["id"], im.get("mime") or "image/jpeg", _blob(raw)))
        except Exception:
            continue
    db.commit()
    return jsonify({"ok": True, "entries_imported": n})


# ---------- Picha za ukurasa ----------
_DATA_URL_RE = re.compile(r"^data:(image/jpeg|image/png|image/webp);base64,(.+)$", re.S)
IMAGE_MAX_BYTES = 3 * 1024 * 1024


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
               (img_id, m.group(1), _blob(raw)))
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
    resp = Response(bytes(row["data"]), mimetype=row["mime"])
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
