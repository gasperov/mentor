#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VENV_DIR="${VENV_DIR:-.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
RUN_DIR="${RUN_DIR:-run}"
PID_FILE="$RUN_DIR/ocenime.pid"
LOG_FILE="$RUN_DIR/ocenime.log"

mkdir -p "$RUN_DIR"

is_running() {
  [[ -f "$PID_FILE" ]] || return 1
  local pid
  pid="$(cat "$PID_FILE")"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

start_server() {
  if is_running; then
    echo "Server is already running (PID $(cat "$PID_FILE"))."
    exit 0
  fi

  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Missing $PYTHON_BIN. Install Python 3 and rerun."
    exit 1
  fi

  if [[ ! -d "$VENV_DIR" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi

  "$VENV_DIR/bin/python" -m pip install --upgrade pip
  "$VENV_DIR/bin/python" -m pip install -r requirements.txt

  if [[ ! -f ".env" ]]; then
    echo "Missing .env file. Create it first (for example: cp .env.example .env)."
    exit 1
  fi

  nohup "$VENV_DIR/bin/python" -m app.main >>"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"

  sleep 1
  if is_running; then
    echo "Server started in background (PID $(cat "$PID_FILE"))."
    echo "Logs: $LOG_FILE"
  else
    echo "Server failed to start. Check logs: $LOG_FILE"
    exit 1
  fi
}

stop_server() {
  if ! is_running; then
    echo "Server is not running."
    rm -f "$PID_FILE"
    exit 0
  fi

  local pid
  pid="$(cat "$PID_FILE")"
  kill "$pid" 2>/dev/null || true

  for _ in {1..20}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$PID_FILE"
      echo "Server stopped."
      exit 0
    fi
    sleep 0.25
  done

  echo "Server did not stop gracefully, sending SIGKILL."
  kill -9 "$pid" 2>/dev/null || true
  rm -f "$PID_FILE"
  echo "Server stopped."
}

status_server() {
  if is_running; then
    echo "Server is running (PID $(cat "$PID_FILE"))."
  else
    echo "Server is not running."
    rm -f "$PID_FILE"
  fi
}

show_logs() {
  if [[ -f "$LOG_FILE" ]]; then
    tail -n 100 -f "$LOG_FILE"
  else
    echo "No log file found at $LOG_FILE"
  fi
}

case "${1:-start}" in
  start)
    start_server
    ;;
  stop)
    stop_server
    ;;
  status)
    status_server
    ;;
  logs)
    show_logs
    ;;
  *)
    echo "Usage: $0 [start|stop|status|logs]"
    exit 1
    ;;
esac
