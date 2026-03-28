#!/usr/bin/env python3
"""
Resource Monitor - Auto-Scale to GCP when usage exceeds 75%
Assignment 3: Cloud Computing
"""

import psutil
import time
import subprocess
import logging
import os
from datetime import datetime

# ─── Configuration ────────────────────────────────────────────────────────────
THRESHOLD        = 75.0          # % CPU or Memory to trigger scale-out
CHECK_INTERVAL   = 30            # seconds between checks
COOLDOWN_PERIOD  = 300           # 5 min cooldown after a scale action
LOG_FILE         = "monitor.log"

# GCP settings (edit these)
GCP_PROJECT      = "your-project-id"
GCP_ZONE         = "us-central1-a"
GCP_INSTANCE_NAME= "autoscale-instance"
GCP_MACHINE_TYPE = "e2-medium"
GCP_IMAGE_FAMILY = "ubuntu-2204-lts"
GCP_IMAGE_PROJECT= "ubuntu-os-cloud"
APP_STARTUP_SCRIPT= "startup.sh"      # uploaded to instance on creation
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# Track state
scaled_out     = False
last_scale_time = 0


def get_cpu_percent(interval: float = 1.0) -> float:
    return psutil.cpu_percent(interval=interval)


def get_memory_percent() -> float:
    return psutil.virtual_memory().percent


def is_instance_running(name: str) -> bool:
    """Check if GCP instance exists and is RUNNING."""
    result = subprocess.run(
        ["gcloud", "compute", "instances", "describe", name,
         "--zone", GCP_ZONE, "--project", GCP_PROJECT,
         "--format=value(status)"],
        capture_output=True, text=True
    )
    return result.returncode == 0 and result.stdout.strip() == "RUNNING"


def create_gcp_instance() -> bool:
    """Spin up a new GCP VM and deploy the sample application."""
    log.info("Creating GCP instance: %s", GCP_INSTANCE_NAME)

    startup = (
        "#!/bin/bash\n"
        "apt-get update -y\n"
        "apt-get install -y python3-pip\n"
        "pip3 install flask\n"
        "cat > /tmp/app.py << 'EOF'\n"
        "from flask import Flask\n"
        "app = Flask(__name__)\n"
        "@app.route('/')\n"
        "def home():\n"
        "    return '<h1>Auto-Scaled App Running on GCP!</h1>'\n"
        "if __name__ == '__main__':\n"
        "    app.run(host='0.0.0.0', port=80)\n"
        "EOF\n"
        "nohup python3 /tmp/app.py &> /tmp/app.log &\n"
    )

    result = subprocess.run([
        "gcloud", "compute", "instances", "create", GCP_INSTANCE_NAME,
        "--project",      GCP_PROJECT,
        "--zone",         GCP_ZONE,
        "--machine-type", GCP_MACHINE_TYPE,
        "--image-family", GCP_IMAGE_FAMILY,
        "--image-project", GCP_IMAGE_PROJECT,
        "--tags",         "http-server",
        "--metadata",     f"startup-script={startup}",
    ], capture_output=True, text=True)

    if result.returncode == 0:
        log.info("GCP instance created successfully.")
        return True
    else:
        log.error("Failed to create instance: %s", result.stderr)
        return False


def delete_gcp_instance() -> bool:
    """Terminate the GCP VM when resources drop back below threshold."""
    log.info("Deleting GCP instance: %s", GCP_INSTANCE_NAME)
    result = subprocess.run([
        "gcloud", "compute", "instances", "delete", GCP_INSTANCE_NAME,
        "--project", GCP_PROJECT,
        "--zone",    GCP_ZONE,
        "--quiet"
    ], capture_output=True, text=True)

    if result.returncode == 0:
        log.info("GCP instance deleted.")
        return True
    else:
        log.error("Failed to delete instance: %s", result.stderr)
        return False


def scale_out():
    global scaled_out, last_scale_time
    if not is_instance_running(GCP_INSTANCE_NAME):
        if create_gcp_instance():
            scaled_out = True
            last_scale_time = time.time()
    else:
        log.info("Instance already running — skipping creation.")
        scaled_out = True


def scale_in():
    global scaled_out
    if is_instance_running(GCP_INSTANCE_NAME):
        if delete_gcp_instance():
            scaled_out = False
    else:
        scaled_out = False


def main():
    global scaled_out, last_scale_time
    log.info("=== Resource Monitor Started (threshold=%.0f%%) ===", THRESHOLD)

    while True:
        cpu = get_cpu_percent()
        mem = get_memory_percent()
        log.info("CPU: %.1f%%  |  Memory: %.1f%%  |  Scaled-out: %s",
                 cpu, mem, scaled_out)

        now = time.time()
        resource_high = cpu > THRESHOLD or mem > THRESHOLD
        cooldown_ok   = (now - last_scale_time) > COOLDOWN_PERIOD

        if resource_high and not scaled_out and cooldown_ok:
            log.warning("THRESHOLD EXCEEDED — triggering scale-out! "
                        "(CPU=%.1f%%, MEM=%.1f%%)", cpu, mem)
            scale_out()

        elif not resource_high and scaled_out and cooldown_ok:
            log.info("Resources back to normal — triggering scale-in.")
            scale_in()

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
