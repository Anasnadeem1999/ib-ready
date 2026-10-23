"""Start Tick & Tie:  python run.py   (then open the printed link)."""

import os
import socket
import sys
import threading
import webbrowser

import uvicorn


def free_port(start: int = 8000) -> int:
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 0)) or free_port()
    url = f"http://127.0.0.1:{port}"
    print(f"\n  Tick & Tie is running at {url}\n  (Ctrl+C to stop)\n")
    if "--no-browser" not in sys.argv:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("ticktie.server:app", host="127.0.0.1", port=port, log_level="warning")
