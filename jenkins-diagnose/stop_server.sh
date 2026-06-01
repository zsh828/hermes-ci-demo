#!/bin/bash
# 停止 Hermes Diagnose HTTP Server

PID_FILE="/tmp/hermes_diagnose_server.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "PID file not found. Server may not be running."
    exit 1
fi

PID=$(cat "$PID_FILE")

if ! kill -0 "$PID" 2>/dev/null; then
    echo "Process $PID is not running. Cleaning up..."
    rm -f "$PID_FILE"
    exit 0
fi

echo "Stopping server (PID: $PID)..."
kill "$PID" 2>/dev/null

# 等待最多5秒
for i in {1..10}; do
    if ! kill -0 "$PID" 2>/dev/null; then
        rm -f "$PID_FILE"
        echo "Server stopped."
        exit 0
    fi
    sleep 0.5
done

echo "Server did not stop gracefully. Force killing..."
kill -9 "$PID" 2>/dev/null
rm -f "$PID_FILE"
echo "Server killed."
