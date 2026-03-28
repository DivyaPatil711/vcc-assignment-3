#!/bin/bash
# setup_full.sh  –  Full setup: webapp + nginx + monitor + dashboard
# Assignment 3 – Cloud Computing
# Run from inside ~/vcc-assignment-3/

set -e
echo "============================================================"
echo " VCC Assignment 3 – Full Architecture Setup"
echo "============================================================"

PROJECT_DIR="$HOME/vcc-assignment-3"
cd "$PROJECT_DIR"

# 1. System packages
echo "[1/7] Installing system packages..."
sudo apt-get update -y
sudo apt-get install -y python3-pip python3-venv nginx curl \
  apt-transport-https ca-certificates gnupg

# 2. Python venv
echo "[2/7] Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install flask psutil

# 3. gcloud (via apt)
echo "[3/7] Installing Google Cloud SDK..."
if ! command -v gcloud &> /dev/null; then
    curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
      sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
    echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] \
https://packages.cloud.google.com/apt cloud-sdk main" | \
      sudo tee /etc/apt/sources.list.d/google-cloud-sdk.list
    sudo apt-get update -y && sudo apt-get install -y google-cloud-cli
    echo "✔ gcloud installed"
else
    echo "✔ gcloud already installed — $(gcloud --version | head -1)"
fi

# 4. Nginx sudoers (allow reload without password)
echo "[4/7] Configuring nginx sudoers..."
echo "$USER ALL=(ALL) NOPASSWD: /usr/sbin/nginx" | sudo tee /etc/sudoers.d/vcc-nginx > /dev/null
sudo chmod 440 /etc/sudoers.d/vcc-nginx

# 5. Initial nginx config (local only to start)
echo "[5/7] Writing initial nginx config..."
sudo mkdir -p /etc/nginx/sites-enabled
sudo tee /etc/nginx/sites-enabled/vcc-webapp.conf > /dev/null << 'NGINXEOF'
upstream vcc_backends {
    server 127.0.0.1:5000 weight=1;
}

server {
    listen 80;
    server_name _;

    location / {
        proxy_pass         http://vcc_backends;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        add_header         X-Served-By $upstream_addr always;
    }

    location /nginx_status {
        stub_status on;
        allow 127.0.0.1;
        deny  all;
    }
}
NGINXEOF

# Remove default nginx site if exists
sudo rm -f /etc/nginx/sites-enabled/default

# Test and reload nginx
sudo nginx -t && sudo nginx -s reload || sudo systemctl start nginx
echo "✔ Nginx configured on port 80"

# 6. Create project directory structure
echo "[6/7] Setting up project files..."
mkdir -p webapp dashboard

# Copy files if they exist, otherwise remind user
for f in webapp/app.py monitor.py dashboard/dashboard.py; do
    if [ -f "$f" ]; then
        echo "  ✔ $f exists"
    else
        echo "  ✗ $f missing — copy it into $PROJECT_DIR/$f"
    fi
done

# 7. Create systemd-style start scripts
echo "[7/7] Creating start scripts..."

cat > start_webapp.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
echo "Starting webapp on port 5000..."
nohup python3 webapp/app.py > webapp.log 2>&1 & echo $! > webapp.pid
echo "Webapp PID: $(cat webapp.pid)"
EOF

cat > start_monitor.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
echo "Starting monitor..."
nohup python3 monitor.py > monitor.log 2>&1 & echo $! > monitor.pid
echo "Monitor PID: $(cat monitor.pid)"
EOF

cat > start_dashboard.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
echo "Starting dashboard on port 8080..."
nohup python3 dashboard/dashboard.py > dashboard.log 2>&1 & echo $! > dashboard.pid
echo "Dashboard PID: $(cat dashboard.pid)"
EOF

cat > start_all.sh << 'EOF'
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
EOF

cat > stop_all.sh << 'EOF'
#!/bin/bash
for pid_file in webapp.pid monitor.pid dashboard.pid; do
    if [ -f "$pid_file" ]; then
        kill $(cat "$pid_file") 2>/dev/null && echo "Stopped $pid_file"
        rm -f "$pid_file"
    fi
done
echo "All services stopped."
EOF

chmod +x start_webapp.sh start_monitor.sh start_dashboard.sh start_all.sh stop_all.sh

IP=$(hostname -I | awk '{print $1}')
echo ""
echo "============================================================"
echo " Setup complete!"
echo ""
echo " NEXT STEPS:"
echo " 1. Set your GCP project in monitor.py (already set to cloudburstarchitecture)"
echo " 2. Run:  bash start_all.sh"
echo ""
echo " URLs:"
echo "   Website:   http://$IP"
echo "   Dashboard: http://$IP:8080"
echo "   Stress:    python3 stress_test.py --cpu 85 --duration 120"
echo "============================================================"
