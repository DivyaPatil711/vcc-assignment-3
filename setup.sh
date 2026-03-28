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
sudo apt-get install -y python3-pip python3-venv git curl unzip \
  apt-transport-https ca-certificates gnupg

# 2. Python dependencies (venv to avoid externally-managed-environment error)
echo "[2/5] Installing Python dependencies in a virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip psutil flask
echo "✔ venv created — activate with: source venv/bin/activate"

# 3. Google Cloud SDK via apt
echo "[3/5] Installing Google Cloud SDK via apt..."

if ! command -v gcloud &> /dev/null; then
    # Add Google's signing key
    curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
      sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg

    # Add the repo
    echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] \
https://packages.cloud.google.com/apt cloud-sdk main" | \
      sudo tee /etc/apt/sources.list.d/google-cloud-sdk.list

    # Install
    sudo apt-get update -y
    sudo apt-get install -y google-cloud-cli

    echo "✔ gcloud installed via apt"
else
    echo "✔ gcloud already installed"
fi

# 4. Verify gcloud
echo "[4/5] Verifying gcloud..."
gcloud --version

# 5. Instructions for auth
echo "[5/5] Next steps — run these manually:"
echo ""
echo "  gcloud auth login"
echo "  gcloud config set project YOUR_PROJECT_ID"
echo "  gcloud services enable compute.googleapis.com"
echo "  gcloud compute firewall-rules create allow-http \\"
echo "    --allow tcp:80 --target-tags http-server --project YOUR_PROJECT_ID"
echo ""
echo "============================================================"
echo " Setup complete! Edit monitor.py with your GCP project ID,"
echo " then run:  source venv/bin/activate && python3 monitor.py"
echo "============================================================"