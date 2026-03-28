#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
echo "Starting webapp on port 5000..."
nohup python3 webapp/app.py > webapp.log 2>&1 & echo $! > webapp.pid
echo "Webapp PID: $(cat webapp.pid)"
