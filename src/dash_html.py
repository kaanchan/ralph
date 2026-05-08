import http.server
import socketserver
import webbrowser
from pathlib import Path
import os

ROOT = Path(__file__).parent.parent

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        if path == "/":
            return str(ROOT / "docs" / "tv_dashboard.html")
        elif path == "/live_state.json":
            return str(ROOT / "logs" / "live_state.json")
        return super().translate_path(path)

def main():
    port = 8080
    with socketserver.TCPServer(("", port), CustomHandler) as httpd:
        print(f"Serving HTML Dashboard on http://localhost:{port}")
        webbrowser.open(f"http://localhost:{port}")
        httpd.serve_forever()

if __name__ == "__main__":
    main()
