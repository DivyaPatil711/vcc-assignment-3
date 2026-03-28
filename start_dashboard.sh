#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
echo "Starting dashboard on port 8080..."
nohup python3 dashboard/dashboard.py > dashboard.log 2>&1 & echo $! > dashboard.pid
echo "Dashboard PID: $(cat dashboard.pid)"
