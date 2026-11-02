#!/usr/bin/env bash
# Recording rig for coding tutorials on a headless Linux box.
#   rig.sh start [PROJECT_DIR]   Xvfb + code-server + (optional) Vite + Chromium showing the stage
#   rig.sh stop                  kill everything this script started
#   rig.sh status                what is up, and a screenshot of the virtual screen
#   rig.sh shot [out.png]        one screenshot of the virtual screen
# Settings (env): WORK (~/tutorial-work) DISPLAY_NUM (99) CS_PORT (8091) CDP_PORT (9333)
#                 VITE_PORT (5173) START_VITE (1 when PROJECT_DIR has package.json) CHROME (auto)
# Every server is started detached with its output in $WORK/logs/*.log, never piped back
# to the caller: a background server holding your stdout pipe is how agent shells hang.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL="$(dirname "$HERE")"
WORK="${WORK:-$HOME/tutorial-work}"
DN="${DISPLAY_NUM:-99}"; CS_PORT="${CS_PORT:-8091}"; CDP_PORT="${CDP_PORT:-9333}"; VITE_PORT="${VITE_PORT:-5173}"
LOG="$WORK/logs"; RUN="$WORK/run"; mkdir -p "$LOG" "$RUN" "$WORK/cs-data/User" "$WORK/cs-ext"

find_chrome() {
  [ -n "${CHROME:-}" ] && { echo "$CHROME"; return; }
  for c in google-chrome chromium chromium-browser; do command -v "$c" >/dev/null && { command -v "$c"; return; }; done
  ls -d "$HOME"/.cache/ms-playwright/chromium-*/chrome-linux*/chrome 2>/dev/null | sort -V | tail -1
}
bg() { # bg NAME LOGFILE CMD... : detached, own session, pid file
  local name=$1 logf=$2; shift 2
  setsid nohup "$@" >"$logf" 2>&1 < /dev/null &
  echo $! >"$RUN/$name.pid"
}
alive() { [ -f "$RUN/$1.pid" ] && kill -0 "$(cat "$RUN/$1.pid")" 2>/dev/null; }
wait_http() { for _ in $(seq 1 "${2:-40}"); do curl -s -o /dev/null -m 2 "$1" && return 0; sleep 0.5; done; return 1; }

start() {
  local project="${1:-}"
  export DISPLAY=":$DN"
  if ! alive xvfb; then
    bg xvfb "$LOG/xvfb.log" Xvfb ":$DN" -screen 0 1920x1080x24 -nolisten tcp -ac
    sleep 1.5
  fi
  cp "$SKILL/templates/code-server-settings.json" "$WORK/cs-data/User/settings.json"
  if ! alive code-server; then
    command -v code-server >/dev/null || { echo "code-server missing: curl -fsSL https://code-server.dev/install.sh | sh"; exit 1; }
    bg code-server "$LOG/code-server.log" env NODE_NO_WARNINGS=1 code-server --auth none --bind-addr "127.0.0.1:$CS_PORT" \
      --user-data-dir "$WORK/cs-data" --extensions-dir "$WORK/cs-ext" --disable-telemetry --disable-update-check \
      --disable-workspace-trust --disable-getting-started-override
    wait_http "http://127.0.0.1:$CS_PORT/" 60 || { echo "code-server did not come up, see $LOG/code-server.log"; exit 1; }
  fi
  if [ -n "$project" ] && [ -f "$project/package.json" ] && [ "${START_VITE:-1}" = "1" ] && ! alive vite; then
    ( cd "$project" && bg vite "$LOG/vite.log" npx vite --port "$VITE_PORT" --strictPort --host 127.0.0.1 )
    wait_http "http://127.0.0.1:$VITE_PORT/" 60 || echo "WARN vite not answering yet, see $LOG/vite.log"
  fi
  cp "$SKILL/templates/harness.html" "$WORK/harness.html"
  if ! alive chrome; then
    local ch; ch="$(find_chrome)"; [ -x "$ch" ] || { echo "no Chromium found: set CHROME=/path/to/chrome"; exit 1; }
    rm -rf "$WORK/chrome-profile"
    bg chrome "$LOG/chrome.log" "$ch" --remote-debugging-port="$CDP_PORT" --user-data-dir="$WORK/chrome-profile" \
      --kiosk --window-position=0,0 --window-size=1920,1080 --force-device-scale-factor=1 --hide-scrollbars \
      --no-first-run --no-default-browser-check --disable-infobars --noerrdialogs --disable-session-crashed-bubble \
      --disable-features=Translate --password-store=basic --test-type --no-sandbox --autoplay-policy=no-user-gesture-required \
      "file://$WORK/harness.html"
    wait_http "http://127.0.0.1:$CDP_PORT/json/version" 40 || { echo "chrome CDP not up, see $LOG/chrome.log"; exit 1; }
  fi
  echo "rig up: DISPLAY=:$DN editor=http://127.0.0.1:$CS_PORT cdp=http://127.0.0.1:$CDP_PORT stage=$WORK/harness.html"
}

stop() {
  for n in chrome vite code-server xvfb; do
    if alive "$n"; then pid=$(cat "$RUN/$n.pid"); kill -TERM -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null; fi
    rm -f "$RUN/$n.pid"
  done
  sleep 1; pkill -f "Xvfb :$DN" 2>/dev/null; pkill -f "remote-debugging-port=$CDP_PORT" 2>/dev/null
  rm -rf "$WORK/chrome-profile"; echo "rig stopped"
}

shot() { DISPLAY=":$DN" timeout -k 2 15 ffmpeg -nostdin -loglevel error -y -f x11grab -video_size 1920x1080 -i ":$DN" -frames:v 1 "${1:-$WORK/shot.png}" && echo "${1:-$WORK/shot.png}"; }

status() {
  for n in xvfb code-server vite chrome; do if alive "$n"; then echo "$n: up (pid $(cat "$RUN/$n.pid"))"; else echo "$n: down"; fi; done
  free -m | awk 'NR==2{print "memory free: "$7" MB"}'; df -h "$WORK" | awk 'NR==2{print "disk free: "$4}'
  alive xvfb && shot
}

case "${1:-}" in
  start) shift; start "${1:-}";;
  stop) stop;;
  status) status;;
  shot) shift; shot "${1:-}";;
  *) echo "usage: rig.sh start [PROJECT_DIR] | stop | status | shot [out.png]"; exit 1;;
esac
