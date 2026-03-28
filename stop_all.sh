#!/bin/bash
echo "Stopping all VCC services..."
pkill -f "python3 monitor.py"    2>/dev/null
pkill -f "python3 webapp/app.py" 2>/dev/null
pkill -f "python3 dashboard/dashboard.py" 2>/dev/null
pkill -f "stress_test.py"        2>/dev/null
sleep 1
rm -f webapp.pid monitor.pid dashboard.pid
echo "All services stopped."
