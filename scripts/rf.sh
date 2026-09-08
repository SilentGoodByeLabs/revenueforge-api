#!/usr/bin/env bash
# rf — RevenueForge one-command launcher
REPO="$HOME/projects/revenue_forge"
WPID="$HOME/.rf_worker.pid";  WLOG="$HOME/.rf_worker.log"
PPID_="$HOME/.rf_private.pid"; PLOG="$HOME/.rf_private.log"
WPIDWEB="$HOME/.rf_web.pid";  WEBLOG="$HOME/.rf_web.log"
cd "$REPO" || exit 1
source .venv/bin/activate 2>/dev/null
alive(){ local p; p=$(cat "$1" 2>/dev/null); [ -n "$p" ] && kill -0 "$p" 2>/dev/null && [ "$(ps -o stat= -p "$p" 2>/dev/null | tr -d " ")" != "Z" ]; }
port_up(){ (exec 3<>/dev/tcp/127.0.0.1/$1) 2>/dev/null && { exec 3>&- 3<&-; return 0; } || return 1; }

start_worker(){ if alive "$WPID"; then echo "  worker: already running"; else nohup python3 scripts/home_worker.py >>"$WLOG" 2>&1 & echo $! > "$WPID"; echo "  ✅ worker started (home-IP search)"; fi; }
start_private(){
  if alive "$PPID_"; then echo "  private engine: already running (rf)";
  elif port_up 8502; then echo "  private engine: already running (your own) — reusing it";
  else nohup python3 -m uvicorn app.ui.webapp:app --host 127.0.0.1 --port 8502 >>"$PLOG" 2>&1 & echo $! > "$PPID_"; echo "  ✅ private engine started (localhost:8502)"; fi; }
start_web(){ if alive "$WPIDWEB"; then echo "  local web: already running"; else nohup python3 -m http.server 8600 --directory website >>"$WEBLOG" 2>&1 & echo $! > "$WPIDWEB"; echo "  ✅ local web started (http://localhost:8600)"; fi; }

case "$1" in
  start|"")
    echo "🚀 RevenueForge starting…"
    start_worker; start_private; start_web
    echo ""; echo "Done.  rf status | rf logs | rf stop"
    echo "Local portal (full home-IP sources): http://localhost:8600/portal.html"
    ;;
  stop)
    for p in "$WPID" "$PPID_" "$WPIDWEB"; do [ -f "$p" ] && kill "$(cat $p)" 2>/dev/null && rm -f "$p"; done
    echo "✅ rf-managed services stopped (your own private engine, if you started it, keeps running)"
    ;;
  status)
    alive "$WPID"    && echo "✅ worker running"    || echo "⛔ worker stopped"
    if alive "$PPID_"; then echo "✅ private engine running (rf, 8502)"; elif port_up 8502; then echo "✅ private engine running (your own, 8502)"; else echo "⛔ private engine stopped"; fi
    alive "$WPIDWEB" && echo "✅ local web running (8600)" || echo "⛔ local web stopped"
    curl -s -o /dev/null -w "cloud health: %{http_code}\n" "https://revenueforge-api.onrender.com/health"
    ;;
  logs) echo "--- worker ---"; tail -n 20 "$WLOG"; echo "--- private ---"; tail -n 10 "$PLOG" ;;
  *) echo "usage: rf [start|stop|status|logs]" ;;
esac
