import heapq
import re
import sqlite3
import threading
from datetime import datetime

from flask import Flask, flash, g, jsonify, redirect, render_template, request, url_for

DB_PATH = "egesha.db"
TOTAL_SLOTS = 20
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

app = Flask(__name__)
app.secret_key = "egesha-dev-key"
lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS slots (
    slot_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_number TEXT NOT NULL UNIQUE,
    status      TEXT NOT NULL DEFAULT 'free' CHECK (status IN ('free','occupied'))
);
CREATE TABLE IF NOT EXISTS sessions (
    session_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    plate       TEXT NOT NULL,
    slot_id     INTEGER NOT NULL REFERENCES slots(slot_id),
    entry_time  TEXT NOT NULL,
    exit_time   TEXT,
    fee         INTEGER,
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','completed'))
);
CREATE TABLE IF NOT EXISTS payments (
    payment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(session_id),
    amount      INTEGER NOT NULL,
    method      TEXT NOT NULL,
    paid_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_plate ON sessions(plate, status);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    if db.execute("SELECT COUNT(*) FROM slots").fetchone()[0] == 0:
        db.executemany("INSERT INTO slots(slot_number) VALUES (?)",
                       [(f"A{i:02d}",) for i in range(1, TOTAL_SLOTS + 1)])
    db.commit()
    db.close()


class SlotManager:
    def __init__(self):
        self.free_heap = []
        self.active = {}

    def load_from_db(self):
        db = sqlite3.connect(DB_PATH)
        self.free_heap = [r[0] for r in db.execute(
            "SELECT slot_id FROM slots WHERE status='free'")]
        heapq.heapify(self.free_heap)
        self.active = {r[0]: r[1] for r in db.execute(
            "SELECT plate, session_id FROM sessions WHERE status='active'")}
        db.close()

    def allocate(self):
        return heapq.heappop(self.free_heap) if self.free_heap else None

    def release(self, slot_id):
        heapq.heappush(self.free_heap, slot_id)


slots = SlotManager()


def calculate_fee(entry_time, exit_time):
    minutes = (exit_time - entry_time).total_seconds() / 60
    if minutes <= 30:
        fee = 0
    elif minutes <= 120:
        fee = 50
    elif minutes <= 240:
        fee = 100
    elif minutes <= 360:
        fee = 300
    else:
        fee = 500
    return fee, int(minutes)


def clean_plate(raw):
    plate = re.sub(r"\s+", "", raw or "").upper()
    return plate if re.fullmatch(r"[A-Z0-9]{5,8}", plate) else None


@app.route("/")
def index():
    rows = get_db().execute("SELECT * FROM slots ORDER BY slot_id").fetchall()
    free = sum(1 for r in rows if r["status"] == "free")
    return render_template("index.html", slots=rows, free=free, total=len(rows))


@app.route("/api/slots")
def api_slots():
    rows = get_db().execute("SELECT slot_number, status FROM slots ORDER BY slot_id")
    data = [dict(r) for r in rows]
    return jsonify(slots=data, free=sum(1 for s in data if s["status"] == "free"))


@app.route("/enter", methods=["POST"])
def enter():
    plate = clean_plate(request.form.get("plate"))
    if not plate:
        flash("Enter a valid number plate (5-8 letters or digits).", "error")
        return redirect(url_for("index"))
    with lock:
        if plate in slots.active:
            flash(f"{plate} is already inside the parking.", "error")
            return redirect(url_for("index"))
        slot_id = slots.allocate()
        if slot_id is None:
            flash("Parking is full. Please try again later.", "error")
            return redirect(url_for("index"))
        db = get_db()
        now = datetime.now().strftime(TIME_FORMAT)
        cur = db.execute("INSERT INTO sessions(plate, slot_id, entry_time) VALUES (?,?,?)",
                         (plate, slot_id, now))
        db.execute("UPDATE slots SET status='occupied' WHERE slot_id=?", (slot_id,))
        db.commit()
        slots.active[plate] = cur.lastrowid
        number = db.execute("SELECT slot_number FROM slots WHERE slot_id=?",
                            (slot_id,)).fetchone()[0]
    flash(f"Welcome {plate}. Park at slot {number}. Entry recorded at {now[11:16]}.", "ok")
    return redirect(url_for("index"))


@app.route("/exit", methods=["GET", "POST"])
def exit_bill():
    bill = None
    if request.method == "POST":
        plate = clean_plate(request.form.get("plate"))
        sid = slots.active.get(plate)
        if not sid:
            flash("No active parking record found for that plate.", "error")
        else:
            s = get_db().execute(
                "SELECT s.*, l.slot_number FROM sessions s JOIN slots l USING(slot_id) "
                "WHERE session_id=?", (sid,)).fetchone()
            fee, mins = calculate_fee(datetime.strptime(s["entry_time"], TIME_FORMAT),
                                      datetime.now())
            bill = {"s": s, "fee": fee, "minutes": mins}
    return render_template("exit.html", bill=bill)


@app.route("/pay", methods=["POST"])
def pay():
    plate = clean_plate(request.form.get("plate"))
    method = request.form.get("method", "Cash")
    with lock:
        sid = slots.active.get(plate)
        if not sid:
            flash("No active parking record found.", "error")
            return redirect(url_for("exit_bill"))
        db = get_db()
        s = db.execute("SELECT * FROM sessions WHERE session_id=?", (sid,)).fetchone()
        now = datetime.now()
        fee, mins = calculate_fee(datetime.strptime(s["entry_time"], TIME_FORMAT), now)
        stamp = now.strftime(TIME_FORMAT)
        db.execute("UPDATE sessions SET exit_time=?, fee=?, status='completed' WHERE session_id=?",
                   (stamp, fee, sid))
        db.execute("INSERT INTO payments(session_id, amount, method, paid_at) VALUES (?,?,?,?)",
                   (sid, fee, method, stamp))
        db.execute("UPDATE slots SET status='free' WHERE slot_id=?", (s["slot_id"],))
        db.commit()
        slots.release(s["slot_id"])
        del slots.active[plate]
    return render_template("barrier.html", plate=plate, fee=fee, minutes=mins, method=method)


@app.route("/admin")
def admin():
    db = get_db()
    history = db.execute(
        "SELECT s.*, l.slot_number FROM sessions s JOIN slots l USING(slot_id) "
        "ORDER BY session_id DESC LIMIT 100").fetchall()
    revenue = db.execute("SELECT COALESCE(SUM(amount),0) FROM payments "
                         "WHERE date(paid_at)=date('now','localtime')").fetchone()[0]
    return render_template("admin.html", history=history, revenue=revenue)


if __name__ == "__main__":
    init_db()
    slots.load_from_db()
    app.run(debug=True)
