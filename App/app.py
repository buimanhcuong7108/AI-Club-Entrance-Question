#!/usr/bin/env python3
"""Trạm học tập lưu động - máy chủ local (chỉ dùng thư viện chuẩn của Python)."""
import json, os, sqlite3, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "tram_hoc_tap.db")
HOST = os.environ.get("HOST", "127.0.0.1")  # đặt HOST=0.0.0.0 để máy khác trong mạng LAN cùng dùng
PORT = int(os.environ.get("PORT", "8000"))
LOCK = threading.Lock()
HTML = "text/html; charset=utf-8"
STATIC = {"/": ("index.html", HTML), "/index.html": ("index.html", HTML),
          "/qrcode.min.js": ("qrcode.min.js", "application/javascript")}


def query(sql, args=()):
    c = sqlite3.connect(DB)
    try:
        c.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK (id = 1), "
                  "v INTEGER NOT NULL, data TEXT NOT NULL)")
        rows = c.execute(sql, args).fetchall()
        c.commit()
        return rows
    finally:
        c.close()


def read_state():
    rows = query("SELECT v, data FROM state WHERE id = 1")
    return (rows[0][0], json.loads(rows[0][1])) if rows else (0, None)


def write_state(client_v, state):
    """Ghi nếu client đang giữ đúng phiên bản; nếu không trả 409 kèm dữ liệu mới nhất."""
    with LOCK:
        v, cur = read_state()
        if client_v != v:
            return 409, {"v": v, "state": cur}
        query("INSERT OR REPLACE INTO state (id, v, data) VALUES (1, ?, ?)",
              (v + 1, json.dumps(state, ensure_ascii=False)))
        return 200, {"v": v + 1}


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, body, ctype="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/state":
            v, s = read_state()
            return self.reply(200, {"v": v, "state": s})
        if path in STATIC:
            name, ctype = STATIC[path]
            f = os.path.join(BASE, name)
            if os.path.isfile(f):
                with open(f, "rb") as fh:
                    return self.reply(200, fh.read(), ctype)
        self.reply(404, {"error": "not found"})

    def do_PUT(self):
        if self.path.split("?")[0] != "/api/state":
            return self.reply(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > 2_000_000:
            return self.reply(413, {"error": "invalid size"})
        try:
            data = json.loads(self.rfile.read(n))
            state, v = data["state"], int(data["v"])
            assert all(isinstance(state.get(k), list) for k in ("docs", "books", "loans"))
            # Quy tắc bản quyền cũng được kiểm tra ở máy chủ: không lưu tài liệu nhóm D
            assert all(d.get("c") in ("A", "B", "C") for d in state["docs"])
        except Exception:
            return self.reply(400, {"error": "bad request"})
        code, body = write_state(v, state)
        self.reply(code, body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Tram hoc tap luu dong dang chay tai http://localhost:{PORT}  (Ctrl+C de dung)")
    print(f"Du lieu luu trong file: {DB}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDa dung.")
