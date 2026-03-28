#!/usr/bin/env python3
"""
monitor.py  -  Resource Monitor with:
  - Local VM CPU/memory tracking
  - GCP instance creation/deletion (scale-out / scale-in)
  - Nginx upstream config auto-update
  - GCP instance CPU monitoring (calls /metrics on each instance)
  - GCP-side autoscaling (if any GCP instance > 75%, create another)
  - Shared state.json for the dashboard

Assignment 3 - Cloud Computing
"""

import psutil, time, subprocess, logging, json, os, urllib.request
from datetime import datetime

# --- Configuration ---------------------------------------------------------
THRESHOLD         = 75.0
CHECK_INTERVAL    = 30
COOLDOWN_PERIOD   = 300       # 5 min between scale actions
MAX_GCP_INSTANCES = 3         # hard cap on cloud VMs

GCP_PROJECT       = "cloudburstarchitecture"
GCP_ZONE          = "us-central1-a"
GCP_MACHINE_TYPE  = "e2-medium"
GCP_IMAGE_FAMILY  = "ubuntu-2204-lts"
GCP_IMAGE_PROJECT = "ubuntu-os-cloud"

LOG_FILE   = "monitor.log"
STATE_FILE = "state.json"
NGINX_CONF = "/etc/nginx/sites-enabled/vcc-webapp.conf"
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# Runtime state
gcp_instances   = {}   # name -> {"ip": str, "cpu": float, "status": str}
last_scale_time = 0    # cooldown guard


# --- Nginx -----------------------------------------------------------------

def write_nginx_conf():
    lines = ["    server 127.0.0.1:5000 weight=1;"]
    for name, info in gcp_instances.items():
        if info.get("ip") and info.get("status") == "RUNNING":
            lines.append(f"    server {info['ip']}:5000 weight=1;  # {name}")

    conf = """upstream vcc_backends {{
{backends}
}}

server {{
    listen 80;
    server_name _;

    location / {{
        proxy_pass         http://vcc_backends;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        add_header         X-Served-By $upstream_addr always;
    }}

    location /nginx_status {{
        stub_status on;
        allow 127.0.0.1;
        deny  all;
    }}
}}
""".format(backends="\n".join(lines))

    try:
        with open(NGINX_CONF, "w") as f:
            f.write(conf)
        result = subprocess.run(["sudo", "nginx", "-s", "reload"],
                                capture_output=True, text=True)
        if result.returncode == 0:
            log.info("Nginx reloaded — %d backend(s) active", len(lines))
        else:
            log.error("Nginx reload failed: %s", result.stderr.strip())
    except Exception as e:
        log.error("Failed to write nginx conf: %s", e)


# --- State -----------------------------------------------------------------

def save_state(local_cpu, local_mem):
    state = {
        "local_cpu":      local_cpu,
        "local_mem":      local_mem,
        "scaled_out":     len(gcp_instances) > 0,
        "instance_count": len(gcp_instances),
        "instances":      [{"name": k, **v} for k, v in gcp_instances.items()],
        "last_update":    datetime.now().isoformat(),
        "threshold":      THRESHOLD,
    }
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# --- GCP helpers -----------------------------------------------------------

def get_instance_ip(name: str):
    r = subprocess.run([
        "gcloud", "compute", "instances", "describe", name,
        "--zone", GCP_ZONE, "--project", GCP_PROJECT,
        "--format=value(networkInterfaces[0].accessConfigs[0].natIP)"
    ], capture_output=True, text=True)
    ip = r.stdout.strip()
    return ip if (r.returncode == 0 and ip) else None


def poll_instance_cpu(ip: str):
    try:
        req = urllib.request.Request(f"http://{ip}:5000/metrics", method="GET")
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read())
            return data.get("cpu_percent")
    except Exception:
        return None


def next_instance_name():
    existing = set(gcp_instances.keys())
    for i in range(MAX_GCP_INSTANCES):
        name = f"autoscale-instance-{i}"
        if name not in existing:
            return name
    return None


# --- Startup script --------------------------------------------------------

STARTUP_SCRIPT = r"""#!/bin/bash
apt-get update -y
apt-get install -y python3-pip python3-venv
python3 -m venv /opt/appenv
/opt/appenv/bin/pip install flask psutil

cat > /tmp/app.py << 'PYEOF'
from flask import Flask, jsonify, render_template_string
import platform, psutil, socket, datetime

app = Flask(__name__)

HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>VCC Auto-Scaled App</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: Arial, sans-serif; background: #f0f4f8; min-height: 100vh;
         display: flex; align-items: center; justify-content: center; padding: 20px; }
  .card { background: white; border-radius: 16px; padding: 40px; max-width: 600px; width: 100%;
          box-shadow: 0 4px 24px rgba(0,0,0,0.08); }
  h1 { font-size: 22px; color: #1a1a2e; margin-bottom: 8px; }
  .badge { display: inline-block; padding: 4px 14px; border-radius: 20px; font-size: 12px;
           font-weight: 600; background: #e6f4ea; color: #137333; margin-bottom: 16px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 20px 0; }
  .stat { background: #f8f9fa; border-radius: 10px; padding: 16px; }
  .stat-val { font-size: 26px; font-weight: 700; color: #1a73e8; }
  .stat-lbl { font-size: 11px; color: #888; margin-top: 4px; text-transform: uppercase; }
  .bar { height: 6px; border-radius: 3px; background: #e8eaed; margin-top: 8px; }
  .bar-fill { height: 100%; border-radius: 3px; }
  .info-row { display: flex; justify-content: space-between; font-size: 13px; color: #666;
              padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
  .info-val { color: #333; font-weight: 500; }
  .footer { margin-top: 20px; font-size: 12px; color: #bbb; text-align: center; }
</style>
<script>setTimeout(() => location.reload(), 5000);</script>
</head>
<body>
<div class="card">
  <span class="badge">GCP Cloud Instance</span>
  <h1>Auto-Scaled Web App</h1>
  <p style="color:#666;margin-bottom:16px">Served by: <strong style="color:#1a73e8">{{ hostname }}</strong></p>
  <div class="grid">
    <div class="stat">
      <div class="stat-val">{{ cpu }}%</div>
      <div class="stat-lbl">CPU Usage</div>
      <div class="bar"><div class="bar-fill" style="width:{{ cpu }}%;background:#1a73e8"></div></div>
    </div>
    <div class="stat">
      <div class="stat-val">{{ mem }}%</div>
      <div class="stat-lbl">Memory</div>
      <div class="bar"><div class="bar-fill" style="width:{{ mem }}%;background:#34a853"></div></div>
    </div>
  </div>
  <div>
    <div class="info-row"><span>Server IP</span><span class="info-val">{{ ip }}</span></div>
    <div class="info-row"><span>Server time</span><span class="info-val">{{ time }}</span></div>
  </div>
  <p class="footer">VCC Assignment 3 - GCP Auto-Scaled Instance</p>
</div>
</body>
</html>'''

@app.route("/")
def home():
    cpu = round(psutil.cpu_percent(interval=0.5), 1)
    mem = round(psutil.virtual_memory().percent, 1)
    return render_template_string(HTML,
        hostname=platform.node(), cpu=cpu, mem=mem,
        ip=socket.gethostbyname(socket.gethostname()),
        time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route("/health")
def health():
    return jsonify({"status": "ok", "hostname": platform.node()})

@app.route("/metrics")
def metrics():
    return jsonify({
        "hostname": platform.node(),
        "cpu_percent": round(psutil.cpu_percent(interval=0.5), 1),
        "memory_percent": round(psutil.virtual_memory().percent, 1),
        "timestamp": datetime.datetime.now().isoformat(),
    })

app.run(host="0.0.0.0", port=5000, debug=False)
PYEOF
nohup /opt/appenv/bin/python3 /tmp/app.py &> /tmp/app.log &
"""


# --- GCP instance lifecycle ------------------------------------------------

def create_gcp_instance(name: str) -> bool:
    log.info("Creating GCP instance: %s", name)

    # Mark PENDING immediately — prevents race conditions where
    # the next loop iteration tries to create the same instance
    gcp_instances[name] = {"ip": None, "cpu": 0.0, "status": "PENDING"}
    save_state(0, 0)

    startup_file = f"/tmp/startup_{name}.sh"
    with open(startup_file, "w") as f:
        f.write(STARTUP_SCRIPT)

    result = subprocess.run([
        "gcloud", "compute", "instances", "create", name,
        "--project",            GCP_PROJECT,
        "--zone",               GCP_ZONE,
        "--machine-type",       GCP_MACHINE_TYPE,
        "--image-family",       GCP_IMAGE_FAMILY,
        "--image-project",      GCP_IMAGE_PROJECT,
        "--tags",               "http-server",
        "--metadata-from-file", f"startup-script={startup_file}",
    ], capture_output=True, text=True)

    if result.returncode == 0:
        log.info("Instance %s created. Waiting 90s for startup script...", name)
        time.sleep(90)
        ip = get_instance_ip(name)
        gcp_instances[name] = {"ip": ip, "cpu": 0.0, "status": "RUNNING"}
        log.info("Instance %s ready. IP: %s", name, ip)
        write_nginx_conf()
        save_state(0, 0)
        return True

    # Instance already exists (leftover from a previous run) — just recover it
    if "already exists" in result.stderr:
        log.warning("Instance %s already exists — recovering", name)
        time.sleep(10)
        ip = get_instance_ip(name)
        gcp_instances[name] = {"ip": ip, "cpu": 0.0, "status": "RUNNING"}
        write_nginx_conf()
        save_state(0, 0)
        return True

    log.error("Failed to create %s: %s", name, result.stderr.strip())
    gcp_instances.pop(name, None)
    return False


def delete_gcp_instance(name: str) -> bool:
    log.info("Deleting GCP instance: %s", name)
    result = subprocess.run([
        "gcloud", "compute", "instances", "delete", name,
        "--project", GCP_PROJECT,
        "--zone",    GCP_ZONE,
        "--quiet"
    ], capture_output=True, text=True)

    if result.returncode == 0:
        gcp_instances.pop(name, None)
        write_nginx_conf()
        log.info("Instance %s deleted.", name)
        return True
    else:
        log.error("Failed to delete %s: %s", name, result.stderr.strip())
        return False


def load_existing_instances():
    """On startup, discover any already-running GCP instances."""
    log.info("Scanning for existing GCP instances...")
    result = subprocess.run([
        "gcloud", "compute", "instances", "list",
        "--project", GCP_PROJECT,
        "--zones",   GCP_ZONE,
        "--filter",  "name~autoscale-instance AND status=RUNNING",
        "--format=value(name,networkInterfaces[0].accessConfigs[0].natIP)"
    ], capture_output=True, text=True)

    if result.returncode == 0:
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split()
            name  = parts[0]
            ip    = parts[1] if len(parts) > 1 else None
            gcp_instances[name] = {"ip": ip, "cpu": 0.0, "status": "RUNNING"}
            log.info("Recovered instance: %s (%s)", name, ip)
        if gcp_instances:
            write_nginx_conf()
            save_state(0, 0)


# --- Scale helpers ---------------------------------------------------------

def scale_out():
    global last_scale_time
    name = next_instance_name()
    if not name:
        log.warning("Max GCP instances (%d) reached — skipping", MAX_GCP_INSTANCES)
        return
    # Skip if already exists or is pending creation
    if name in gcp_instances:
        log.info("Instance %s already exists/pending — skipping", name)
        return
    if create_gcp_instance(name):
        last_scale_time = time.time()


def scale_in():
    global last_scale_time
    log.info("Resources normal — scaling in")
    for name in list(gcp_instances.keys()):
        delete_gcp_instance(name)
    last_scale_time = time.time()


# --- Main loop -------------------------------------------------------------

def main():
    global last_scale_time
    log.info("=== Resource Monitor Started (threshold=%.0f%%, max_instances=%d) ===",
             THRESHOLD, MAX_GCP_INSTANCES)

    # Recover any pre-existing GCP instances before writing initial conf
    load_existing_instances()
    write_nginx_conf()

    while True:
        now         = time.time()
        cpu         = round(psutil.cpu_percent(interval=1.0), 1)
        mem         = round(psutil.virtual_memory().percent, 1)
        n_inst      = len(gcp_instances)
        cooldown_ok = (now - last_scale_time) > COOLDOWN_PERIOD

        log.info("CPU: %.1f%%  |  Memory: %.1f%%  |  GCP instances: %d", cpu, mem, n_inst)

        # 1. Poll each GCP instance and check for GCP-side scale-out
        for name in list(gcp_instances.keys()):
            info   = gcp_instances[name]
            status = info.get("status")
            ip     = info.get("ip")

            if status == "PENDING" or not ip:
                log.info("  GCP %s: %s (waiting for startup)", name, status)
                continue

            inst_cpu = poll_instance_cpu(ip)
            if inst_cpu is not None:
                gcp_instances[name]["cpu"] = inst_cpu
                log.info("  GCP %s CPU: %.1f%%", name, inst_cpu)
                if inst_cpu > THRESHOLD and n_inst < MAX_GCP_INSTANCES and cooldown_ok:
                    log.warning("GCP %s overloaded (%.1f%%) — adding another", name, inst_cpu)
                    scale_out()
            else:
                log.warning("  GCP %s unreachable (may still be starting up)", name)

        # 2. Local VM threshold check
        resource_high = cpu > THRESHOLD or mem > THRESHOLD
        no_instances  = len(gcp_instances) == 0  # nothing, not even pending
        running_names = [n for n, i in gcp_instances.items() if i.get("status") == "RUNNING"]

        if resource_high and no_instances and cooldown_ok:
            log.warning("LOCAL THRESHOLD EXCEEDED (CPU=%.1f%%, MEM=%.1f%%) — scale-out",
                        cpu, mem)
            scale_out()

        elif not resource_high and len(running_names) > 0 and cooldown_ok:
            scale_in()

        # 3. Save state for dashboard
        save_state(cpu, mem)

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()