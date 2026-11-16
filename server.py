#!/usr/bin/env python3
"""Unified Local + LAN Web Server for SJKC Hub 2027 (eRPH-PM + Exam Generator).

Pure Python stdlib — zero external dependencies required.
Serves:
  - `/` (`index.html`, `curriculum-db.js`, `rpt-data.js`, `exam-browser.js`, `tailwind.css`)
  - `POST /api/exam` (`api/exam.py` -> full UPSA/UASA exam paper generator)
  - `POST /api/generate-content` (`api/generate_content.py` -> KSSR AI RPH generator)

Usage:
  python3 server.py [--port 8080] [--host 0.0.0.0]
"""

from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from api.exam import handle_exam_request
from api.generate_content import handle_ai_content


class HubRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(raw or "{}")
        except Exception:
            payload = {}

        if path in ("/api/exam", "/api/exam.py"):
            try:
                res = handle_exam_request(payload)
                self._send_json(200, res)
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if path in ("/api/generate-content", "/api/generate_content.py"):
            try:
                res = handle_ai_content(payload)
                self._send_json(200, res)
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if path == "/api/login":
            self._send_json(200, {"ok": True})
            return

        self._send_json(404, {"ok": False, "error": f"Unknown endpoint: {path}"})

    def _send_json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description="SJKC Hub 2027 Web Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), HubRequestHandler)
    print(f"🇲🇾 SJKC Hub 2027 (eRPH-PM + Exam Generator) running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        server.server_close()


if __name__ == "__main__":
    main()
