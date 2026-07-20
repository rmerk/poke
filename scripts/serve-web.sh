#!/usr/bin/env bash
# Serve the iPhone Safari app on LAN (default port 8080).
set -euo pipefail
cd "$(dirname "$0")/../web"
PORT="${1:-8080}"
IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo 'YOUR-MAC-IP')"
echo "Pocket Pokedex (offline web UI)"
echo "  On this Mac:  http://127.0.0.1:${PORT}"
echo "  On iPhone:    http://${IP}:${PORT}"
echo "Same LAN is enough — no internet required at runtime."
echo "Open that URL in Safari on the A1533."
# no-store on every response: iOS Safari caches js/ aggressively, and a stale
# script silently masks edits while you iterate on the device.
exec python3 -c '
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        SimpleHTTPRequestHandler.end_headers(self)

HTTPServer(("", int(sys.argv[1])), NoCacheHandler).serve_forever()
' "$PORT"
