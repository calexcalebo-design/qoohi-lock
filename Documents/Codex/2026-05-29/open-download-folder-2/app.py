from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import json
import os
import re
import secrets
import time


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "cafe.sqlite3")
HOST = "0.0.0.0"
PORT = int(os.environ.get("CAFE_PORT", os.environ.get("PORT", "8080")))
ADMIN_PIN = os.environ.get("CAFE_ADMIN_PIN", "1234")

DATABASE_URL = os.environ.get("DATABASE_URL")


PRICE_PLANS = [
    {"id": "10min", "label": "10 KSh - 10 minutes", "amount": 10, "minutes": 10},
    {"id": "1hr", "label": "50 KSh - 1 hour", "amount": 50, "minutes": 60},
]


def now_ts():
    return int(time.time())


# ---------------------------------------------------------------------------
# Database abstraction -- SQLite (local) or PostgreSQL (Render)
# ---------------------------------------------------------------------------

if DATABASE_URL:
    import psycopg2
    import psycopg2.extras

    class _DB:
        def __init__(self):
            self.conn = psycopg2.connect(DATABASE_URL)
            self.cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        def execute(self, sql, params=None):
            self.cur.execute(sql, params)
            return self

        def fetchall(self):
            return self.cur.fetchall()

        def fetchone(self):
            return self.cur.fetchone()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            try:
                if exc_type is None:
                    self.conn.commit()
                else:
                    self.conn.rollback()
            finally:
                self.cur.close()
                self.conn.close()

        def __iter__(self):
            return iter(self.cur)

    PL = "%s"
    DB_ENGINE = "pg"

    def db():
        return _DB()

    def init_db():
        PG = True
        with db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS computers (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    ip_address TEXT NOT NULL DEFAULT '',
                    message TEXT NOT NULL DEFAULT '',
                    token TEXT NOT NULL UNIQUE,
                    created_at INTEGER NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id SERIAL PRIMARY KEY,
                    computer_id INTEGER NOT NULL REFERENCES computers(id),
                    customer_name TEXT,
                    amount_ksh INTEGER NOT NULL,
                    minutes INTEGER NOT NULL,
                    started_at INTEGER NOT NULL,
                    ends_at INTEGER NOT NULL,
                    stopped_at INTEGER
                )
            """)
            _ensure_column_pg(conn, "computers", "ip_address", "TEXT NOT NULL DEFAULT ''")
            _ensure_column_pg(conn, "computers", "message", "TEXT NOT NULL DEFAULT ''")

    def _ensure_column_pg(conn, table, column, definition):
        conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
            (table, column),
        )
        if not conn.fetchone():
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

else:
    import sqlite3

    PL = "?"
    DB_ENGINE = "sqlite"

    class _SQLiteDB:
        """Wrapper to ensure SQLite connections are closed after use."""
        def __init__(self):
            self.conn = sqlite3.connect(DB_PATH)
            self.conn.row_factory = sqlite3.Row

        def execute(self, sql, params=None):
            # Returns a cursor which supports .fetchone() and .fetchall()
            return self.conn.execute(sql, params or ())

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()

    def db():
        return _SQLiteDB()

    def init_db():
        with db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS computers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    ip_address TEXT NOT NULL DEFAULT '',
                    message TEXT NOT NULL DEFAULT '',
                    token TEXT NOT NULL UNIQUE,
                    created_at INTEGER NOT NULL
                )
            """)
            _ensure_column_sqlite(conn, "computers", "ip_address", "TEXT NOT NULL DEFAULT ''")
            _ensure_column_sqlite(conn, "computers", "message", "TEXT NOT NULL DEFAULT ''")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    computer_id INTEGER NOT NULL,
                    customer_name TEXT,
                    amount_ksh INTEGER NOT NULL,
                    minutes INTEGER NOT NULL,
                    started_at INTEGER NOT NULL,
                    ends_at INTEGER NOT NULL,
                    stopped_at INTEGER,
                    FOREIGN KEY (computer_id) REFERENCES computers (id)
                )
            """)

    def _ensure_column_sqlite(conn, table, column, definition):
        columns = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------


def computer_rows():
    with db() as conn:
        computers = conn.execute(f"SELECT * FROM computers ORDER BY id").fetchall()
        rows = []
        for computer in computers:
            session = conn.execute(
                f"SELECT * FROM sessions WHERE computer_id = {PL} AND stopped_at IS NULL ORDER BY id DESC LIMIT 1",
                (computer["id"],),
            ).fetchone()
            rows.append(serialize_computer(computer, session))
        return rows


def serialize_computer(computer, session=None):
    current = now_ts()
    active = bool(session and session["ends_at"] > current)
    remaining = max(0, session["ends_at"] - current) if session else 0
    expired = bool(session and not session["stopped_at"] and session["ends_at"] <= current)
    return {
        "id": computer["id"],
        "name": computer["name"],
        "ip_address": computer["ip_address"],
        "message": computer["message"],
        "token": computer["token"],
        "customer_url": f"/customer/{computer['id']}?token={computer['token']}",
        "status": "active" if active else "expired" if expired else "locked",
        "remaining_seconds": remaining,
        "session": dict(session) if session else None,
    }


def get_computer(computer_id):
    with db() as conn:
        computer = conn.execute(f"SELECT * FROM computers WHERE id = {PL}", (computer_id,)).fetchone()
        if not computer:
            return None
        session = conn.execute(
            f"SELECT * FROM sessions WHERE computer_id = {PL} AND stopped_at IS NULL ORDER BY id DESC LIMIT 1",
            (computer_id,),
        ).fetchone()
        return serialize_computer(computer, session)


def find_price(plan_id):
    return next((plan for plan in PRICE_PLANS if plan["id"] == plan_id), PRICE_PLANS[0])


def add_computer(name, ip_address=""):
    with db() as conn:
        # Optimized: Just count the computers instead of fetching all session data
        count = conn.execute(f"SELECT COUNT(*) as total FROM computers").fetchone()["total"]
        cleaned = name.strip() or f"PC {count + 1}"
        conn.execute(
            f"INSERT INTO computers (name, ip_address, message, token, created_at) VALUES ({PL}, {PL}, {PL}, {PL}, {PL})",
            (cleaned, ip_address.strip(), "", secrets.token_urlsafe(16), now_ts()),
        )


def get_session_history():
    with db() as conn:
        rows = conn.execute(f"""
            SELECT s.*, c.name as pc_name 
            FROM sessions s 
            JOIN computers c ON s.computer_id = c.id 
            WHERE s.stopped_at IS NOT NULL 
            ORDER BY s.stopped_at DESC 
            LIMIT 50
        """).fetchall()
        return [dict(r) for r in rows]


def update_computer(computer_id, name, ip_address, message=""):
    with db() as conn:
        conn.execute(
            f"UPDATE computers SET name = {PL}, ip_address = {PL}, message = {PL} WHERE id = {PL}",
            (name.strip() or f"PC {computer_id}", ip_address.strip(), message.strip(), computer_id),
        )


def start_session(computer_id, plan_id):
    plan = find_price(plan_id)
    current = now_ts()
    with db() as conn:
        conn.execute(
            f"UPDATE sessions SET stopped_at = {PL} WHERE computer_id = {PL} AND stopped_at IS NULL",
            (current, computer_id),
        )
        conn.execute(
            f"INSERT INTO sessions (computer_id, customer_name, amount_ksh, minutes, started_at, ends_at, stopped_at) VALUES ({PL}, {PL}, {PL}, {PL}, {PL}, {PL}, NULL)",
            (computer_id, "", plan["amount"], plan["minutes"], current, current + plan["minutes"] * 60),
        )


def add_time(computer_id, plan_id):
    plan = find_price(plan_id)
    current = now_ts()
    extra = plan["minutes"] * 60
    with db() as conn:
        session = conn.execute(
            f"SELECT * FROM sessions WHERE computer_id = {PL} AND stopped_at IS NULL ORDER BY id DESC LIMIT 1",
            (computer_id,),
        ).fetchone()
        if session and session["ends_at"] > current:
            conn.execute(
                f"UPDATE sessions SET ends_at = ends_at + {PL}, amount_ksh = amount_ksh + {PL}, minutes = minutes + {PL} WHERE id = {PL}",
                (extra, plan["amount"], plan["minutes"], session["id"]),
            )
        else:
            start_session(computer_id, plan_id)


def stop_session(computer_id):
    with db() as conn:
        conn.execute(
            f"UPDATE sessions SET stopped_at = {PL} WHERE computer_id = {PL} AND stopped_at IS NULL",
            (now_ts(), computer_id),
        )


# ---------------------------------------------------------------------------
# HTML pages
# ---------------------------------------------------------------------------


def html_page(title, body, extra_class=""):
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="/static/styles.css">
</head>
<body class="{extra_class}">
{body}
</body>
</html>"""


def login_page(error=""):
    error_html = f'<p class="error">{error}</p>' if error else ""
    return html_page(
        "QOOHI Login",
        f"""
<main class="login-shell">
  <form class="login-panel" method="post" action="/login">
    <p class="brand-mark">QOOHI</p>
    <h1>Operator Login</h1>
    {error_html}
    <input name="pin" type="password" inputmode="numeric" placeholder="Admin PIN" autofocus>
    <button type="submit">Open dashboard</button>
  </form>
</main>
""",
    )


def admin_page():
    plans = "".join(
        f'<option value="{plan["id"]}">{plan["label"]}</option>' for plan in PRICE_PLANS
    )
    return html_page(
        "QOOHI",
        f"""
<header class="topbar">
  <div>
    <p class="brand-mark">QOOHI</p>
  </div>
  <form class="add-pc" data-add-computer>
    <input name="name" placeholder="New PC name" maxlength="30">
    <input name="ip_address" placeholder="IP address">
    <button type="submit">Add PC</button>
  </form>
</header>

<main class="admin-shell">
  <section class="summary">
    <div><span id="active-count">0</span><small>Active</small></div>
    <div><span id="locked-count">0</span><small>Locked</small></div>
    <div><span id="cash-total">0</span><small>KSh running</small></div>
  </section>
  <section id="empty-state" class="empty-state">
    <h2>No customer PCs added</h2>
    <p>Add the two customer computers by name and IP address. This admin PC stays as the controller.</p>
  </section>
  <section id="computer-grid" class="computer-grid" aria-live="polite"></section>

  <section class="history-section">
    <h2 class="section-title">Recent Session History</h2>
    <div class="table-wrap">
      <table class="history-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>PC Name</th>
            <th>Duration</th>
            <th>Amount</th>
          </tr>
        </thead>
        <tbody id="history-table-body"></tbody>
      </table>
    </div>
  </section>
</main>

<template id="computer-card-template">
  <article class="computer-card">
    <div class="computer-head">
      <div>
        <h2 data-name></h2>
        <p data-status></p>
      </div>
      <strong data-time></strong>
    </div>
    <div class="meter"><span data-meter></span></div>
    <form data-settings-form class="settings-grid">
      <input name="name" placeholder="PC name">
      <input name="ip_address" placeholder="IP address">
      <input name="message" placeholder="Message to customer">
      <button type="submit">Save</button>
    </form>
    <form data-start-form class="control-grid">
      <select name="plan_id">{plans}</select>
      <button type="submit">Start</button>
    </form>
    <div class="button-row">
      <button data-add-time value="10min">+10 min</button>
      <button data-add-time value="1hr">+1 hr</button>
      <button data-stop>Lock</button>
    </div>
    <p class="agent-line" data-agent></p>
    <a data-link target="_blank" rel="noreferrer">Open customer screen</a>
  </article>
</template>

<script src="/static/admin.js"></script>
""",
    )


def customer_page(computer_id, token=""):
    return html_page(
        "QOOHI Customer",
        f"""
<main class="customer-shell" data-computer-id="{computer_id}" data-token="{token}">
  <div class="timer-strip">
    <span id="top-pc-name">QOOHI</span>
    <strong id="top-remaining-time">00:00</strong>
  </div>
  <section class="customer-panel">
    <p class="brand-mark" id="pc-name">QOOHI</p>
    <h1 id="session-state">Locked</h1>
    <div class="big-time" id="remaining-time">00:00</div>
    <p id="customer-note">Please pay at the counter to start a session.</p>
    <div class="meter customer-meter"><span id="meter-fill"></span></div>
  </section>
  <section class="blocked" id="blocked-screen">
    <div>
      <h2>Time expired</h2>
      <p id="blocked-message">Ask the operator to add time from the admin computer.</p>
    </div>
  </section>
</main>
<script src="/static/customer.js"></script>
""",
        "customer-body",
    )


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


class CafeHandler(BaseHTTPRequestHandler):
    def send_text(self, content, status=200, content_type="text/html; charset=utf-8"):
        encoded = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_json(self, payload, status=200):
        self.send_text(json.dumps(payload), status, "application/json; charset=utf-8")

    def read_form(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return {key: values[0] for key, values in parse_qs(raw).items()}

    def is_admin(self):
        cookie = self.headers.get("Cookie", "")
        return "cafe_admin=1" in cookie

    def require_admin(self):
        if self.is_admin():
            return True
        self.send_json({"error": "admin login required"}, 401)
        return False

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") if len(parsed.path) > 1 else parsed.path
        query = parse_qs(parsed.query)

        if path == "/":
            self.send_response(302)
            self.send_header("Location", "/admin")
            self.end_headers()
            return
        if path == "/admin":
            self.send_text(admin_page() if self.is_admin() else login_page())
            return
        if path == "/api/debug/db":
            try:
                with db() as conn:
                    # Check connection and table existence
                    pc_count = conn.execute("SELECT COUNT(*) as total FROM computers").fetchone()["total"]
                    self.send_json({
                        "status": "connected",
                        "engine": DB_ENGINE,
                        "computer_count": pc_count
                    })
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, 500)
            return
        if path == "/logout":
            self.send_response(302)
            self.send_header("Location", "/admin")
            self.send_header("Set-Cookie", "cafe_admin=; Max-Age=0; Path=/; SameSite=Lax")
            self.end_headers()
            return
        match = re.fullmatch(r"/customer/(\d+)", path)
        if match:
            token = (query.get("token") or [""])[0]
            self.send_text(customer_page(int(match.group(1)), token))
            return
        if path == "/api/computers":
            if not self.require_admin():
                return
            self.send_json({"computers": computer_rows(), "plans": PRICE_PLANS})
            return
        if path == "/api/history":
            if not self.require_admin():
                return
            self.send_json({"history": get_session_history()})
            return
        match = re.fullmatch(r"/api/computers/(\d+)", path)
        if match:
            computer_id = int(match.group(1))
            token = (query.get("token") or [""])[0]
            computer = get_computer(computer_id)
            if computer is None:
                self.send_json({"error": "not found"}, 404)
                return
            if token != computer.get("token", ""):
                self.send_json({"error": "invalid token"}, 403)
                return
            self.send_json(computer)
            return
        if path.startswith("/static/"):
            self.serve_static(path)
            return
        self.send_text("Not found", 404, "text/plain; charset=utf-8")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") if len(parsed.path) > 1 else parsed.path
        form = self.read_form()
        if path == "/login":
            if form.get("pin", "") == ADMIN_PIN:
                self.send_response(302)
                self.send_header("Location", "/admin")
                self.send_header("Set-Cookie", "cafe_admin=1; Path=/; SameSite=Lax")
                self.end_headers()
            else:
                self.send_text(login_page("Wrong PIN. Try again."), 401)
            return
        if path == "/api/computers":
            if not self.require_admin():
                return
            add_computer(form.get("name", ""), form.get("ip_address", ""))
            self.send_json({"ok": True})
            return
        match = re.fullmatch(r"/api/computers/(\d+)/(settings|start|add-time|stop)", path)
        if not match:
            self.send_json({"error": "not found"}, 404)
            return
        if not self.require_admin():
            return
        computer_id = int(match.group(1))
        action = match.group(2)
        if action == "settings":
            update_computer(
                computer_id,
                form.get("name", ""),
                form.get("ip_address", ""),
                form.get("message", ""),
            )
        elif action == "start":
            start_session(computer_id, form.get("plan_id", "10min"))
        elif action == "add-time":
            add_time(computer_id, form.get("plan_id", "10min"))
        elif action == "stop":
            stop_session(computer_id)
        self.send_json({"ok": True})

    def serve_static(self, path):
        static_path = os.path.join(BASE_DIR, path.lstrip("/").replace("/", os.sep))
        if not os.path.abspath(static_path).startswith(os.path.join(BASE_DIR, "static")):
            self.send_text("Forbidden", 403, "text/plain; charset=utf-8")
            return
        if not os.path.exists(static_path):
            self.send_text("Not found", 404, "text/plain; charset=utf-8")
            return
        
        if static_path.endswith(".css"):
            content_type = "text/css"
        elif static_path.endswith(".js"):
            content_type = "application/javascript"
        else:
            content_type = "application/octet-stream"

        with open(static_path, "rb") as file:
            content = file.read()
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    init_db()
    print(f"QOOHI running at http://127.0.0.1:{PORT}")
    print(f"Admin page: http://127.0.0.1:{PORT}/admin")
    print("Use your PC LAN IP instead of 127.0.0.1 from customer computers.")
    print(f"DB engine: {DB_ENGINE}" + ("  (set DATABASE_URL for PostgreSQL)" if not DATABASE_URL else ""))
    ThreadingHTTPServer((HOST, PORT), CafeHandler).serve_forever()
