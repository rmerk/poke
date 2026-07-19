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
exec python3 -m http.server "$PORT"
