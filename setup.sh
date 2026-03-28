#!/bin/bash
# setup.sh – Run this ONCE on the local VM to install all dependencies
# Assignment 3 – Cloud Computing

set -e
echo "============================================================"
echo " Assignment 3 – Local VM Resource Monitor Setup"
echo "============================================================"

# 1. System packages
echo "[1/5] Updating system packages..."
sudo apt-get update -y
sudo apt-get install -y python3-pip python3-venv git curl unzip

# 2. Python dependencies
echo "[2/5] Installing Python dependencies..."
pip3 install psutil flask

# 3. Google Cloud SDK
echo "[3/5] Installing Google Cloud SDK..."
if ! command -v gcloud &> /dev/null; then
    curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-latest-linux-x86_64.tar.gz
    tar -xf google-cloud-cli-latest-linux-x86_64.tar.gz
    ./google-cloud-sdk/install.sh --quiet
    source ./google-cloud-sdk/path.bash.inc
    rm google-cloud-cli-latest-linux-x86_64.tar.gz
    echo "✔ gcloud installed"
else
    echo "✔ gcloud already installed"
fi

# 4. Authenticate with GCP (interactive – follow prompts)
echo "[4/5] GCP authentication..."
echo "Run: gcloud auth login && gcloud config set project YOUR_PROJECT_ID"

# 5. Create firewall rule to allow HTTP on GCP
echo "[5/5] Optional: GCP firewall rule for port 80..."
echo "Run after auth: gcloud compute firewall-rules create allow-http \\"
echo "  --allow tcp:80 --target-tags http-server --project YOUR_PROJECT_ID"

echo ""
echo "============================================================"
echo " Setup complete! Edit monitor.py with your GCP project ID,"
echo " then run:  python3 monitor.py"
echo "============================================================"
