#!/bin/bash
# 启动 Hermes Diagnose HTTP Server

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/hermes_diagnose_server.log"
PID_FILE="/tmp/hermes_diagnose_server.pid"

cd "$SCRIPT_DIR"

# 检查是否已运行
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Server is already running (PID: $(cat "$PID_FILE"))"
    exit 0
fi

# 启动服务
echo "Starting Hermes Diagnose Server..."
python3 "$SCRIPT_DIR/diagnose_server.py" >> "$LOG_FILE" 2>&1 &
PID=$!
echo $PID > "$PID_FILE"

sleep 1

# 检查是否启动成功
if kill -0 "$PID" 2>/dev/null; then
    echo "Server started successfully (PID: $PID)"
    echo "Log file: $LOG_FILE"
else
    echo "Failed to start server. Check log: $LOG_FILE"
    exit 1
fi
