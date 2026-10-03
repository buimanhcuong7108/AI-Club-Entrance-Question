#!/usr/bin/env python3
"""Trạm học tập lưu động - máy chủ local (chỉ dùng thư viện chuẩn của Python)."""
import csv, io, json, os, sqlite3, threading
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


EXPORTS = ("docs", "books", "loans")


def _safe(x):
    """Chống chèn công thức khi mở CSV bằng Excel."""
    return "'" + x if isinstance(x, str) and x[:1] in ("=", "+", "-", "@") else x


def _rows(name, s):
    books = {b["id"]: b for b in s["books"]}
    yes = lambda v: "có" if v else "không"
    if name == "docs":
        yield ["id", "Tên tài liệu", "Môn", "Lớp", "Nhóm", "Liên kết", "Ghi chú", "Đã lưu trữ"]
        for d in s["docs"]:
            yield [d["id"], d.get("t"), d.get("s"), d.get("g"), d.get("c"), d.get("l"), d.get("n"), yes(d.get("arch"))]
    elif name == "books":
        out = {}
        for l in s["loans"]:
            if not l.get("ret"):
                out[l["book"]] = out.get(l["book"], 0) + 1
        yield ["id", "Tên sách", "Tổng số bản", "Còn lại"]
        for b in s["books"]:
            yield [b["id"], b["t"], b["total"], b["total"] - out.get(b["id"], 0)]
    else:
        yield ["id", "Học sinh", "Lớp", "Sách", "Hạn trả", "Đã trả"]
        for l in s["loans"]:
            yield [l["id"], l["who"], l["cls"], books.get(l["book"], {}).get("t", "(đã xóa)"), l["due"], yes(l.get("ret"))]


def to_csv(name, s):
    """CSV mã hóa UTF-8 có BOM để Excel đọc đúng tiếng Việt."""
    buf = io.StringIO()
    csv.writer(buf).writerows([_safe(c) for c in row] for row in _rows(name, s))
    return buf.getvalue().encode("utf-8-sig")


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, body, ctype="application/json; charset=utf-8", filename=None):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/state":
            v, s = read_state()
            return self.reply(200, {"v": v, "state": s})
        if path.startswith("/export/") and path.endswith(".csv") and path[8:-4] in EXPORTS:
            _, st = read_state()
            if st:
                return self.reply(200, to_csv(path[8:-4], st), "text/csv; charset=utf-8", filename=path[8:])
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
