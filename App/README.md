# Trạm học tập lưu động (bản chạy local)

Yêu cầu: Python 3.8 trở lên. Không cần cài thêm thư viện nào.

1. Giải nén thư mục, mở terminal tại đây.
2. Chạy: `python app.py` (macOS/Linux: `python3 app.py`)
3. Mở trình duyệt: http://localhost:8000

- Cho máy khác trong cùng mạng Wi-Fi/LAN dùng chung: chạy `HOST=0.0.0.0 python3 app.py`
  (Windows PowerShell: `$env:HOST="0.0.0.0"; python app.py`), rồi mở http://<IP-máy-này>:8000
- Đổi cổng: `PORT=8080 python3 app.py`
- Dừng: Ctrl+C
