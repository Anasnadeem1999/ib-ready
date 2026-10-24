"""Start the app:  python run.py   (then open the printed link). Options: --no-browser, PORT=xxxx."""

import os
import socket
import sys
import threading
import webbrowser

if sys.version_info < (3, 11):  # pydantic-ai needs 3.11+; say so plainly instead of failing on an import
    sys.exit(f"IB Ready needs Python 3.11 or newer; this is {sys.version.split()[0]}. See README step 0.")

import uvicorn  # noqa: E402

from ibready.config import APP_NAME, key_source  # noqa: E402  (also loads .env: repo folder, then the folder above)


def free_port(start: int = 8000) -> int:
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 0)) or free_port()
    url = f"http://127.0.0.1:{port}"
    key = key_source()
    print(f"\n  {APP_NAME} is running at {url}\n  (Ctrl+C to stop)\n"
          + (f"  API key: {key} found\n" if key else
             "  WARNING: no PORTKEY_API_KEY or OPENAI_API_KEY found in .env (this folder or the one above).\n"
             "  The app opens, but answers can't be graded until a key is set.\n"))
    if "--no-browser" not in sys.argv:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("ibready.server:app", host="127.0.0.1", port=port, log_level="warning")
