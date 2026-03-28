#!/bin/bash
cd "$(dirname "$0")"
echo "=== Starting all VCC services ==="
bash start_webapp.sh
sleep 1
bash start_monitor.sh
sleep 1
bash start_dashboard.sh
echo ""
echo "All services started!"
echo "  Website:   http://$(hostname -I | awk '{print $1}'):80"
echo "  Dashboard: http://$(hostname -I | awk '{print $1}'):8080"
echo ""
echo "Logs:"
echo "  tail -f monitor.log    # monitor"
echo "  tail -f webapp.log     # webapp"
echo "  tail -f dashboard.log  # dashboard"
