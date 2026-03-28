#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
echo "Starting monitor..."
nohup python3 monitor.py > monitor.log 2>&1 & echo $! > monitor.pid
echo "Monitor PID: $(cat monitor.pid)"
