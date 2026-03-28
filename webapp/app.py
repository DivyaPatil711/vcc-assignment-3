#!/usr/bin/env python3
"""
webapp/app.py  –  The actual website served through nginx.
Shows which server (local or GCP) handled each request.
Run on port 5000 on ALL instances (local + GCP).
"""
from flask import Flask, jsonify, render_template_string, request
import platform, psutil, socket, datetime

app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VCC Auto-Scaled App</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #f0f4f8; min-height: 100vh;
         display: flex; align-items: center; justify-content: center; padding: 20px; }
  .card { background: white; border-radius: 16px; padding: 40px; max-width: 640px; width: 100%;
          box-shadow: 0 4px 24px rgba(0,0,0,0.08); }
  .header { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; }
  .dot { width: 14px; height: 14px; border-radius: 50%; background: #34a853; flex-shrink: 0; }
  h1 { font-size: 22px; color: #1a1a2e; }
  .badge { display: inline-block; padding: 4px 14px; border-radius: 20px; font-size: 12px;
           font-weight: 600; letter-spacing: 0.5px; }
  .badge-local { background: #e8f0fe; color: #1a73e8; }
  .badge-cloud { background: #e6f4ea; color: #137333; }
  .server-name { font-size: 18px; color: #444; margin: 8px 0 20px; }
  .server-name strong { color: #1a73e8; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 24px; }
  .stat { background: #f8f9fa; border-radius: 10px; padding: 16px; }
  .stat-val { font-size: 26px; font-weight: 700; color: #1a73e8; }
  .stat-lbl { font-size: 11px; color: #888; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
  .bar { height: 6px; border-radius: 3px; background: #e8eaed; margin-top: 8px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
  .bar-fill.cpu { background: #1a73e8; }
  .bar-fill.mem { background: #34a853; }
  .info-row { display: flex; justify-content: space-between; font-size: 13px; color: #666;
              padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
  .info-row:last-child { border-bottom: none; }
  .info-val { color: #333; font-weight: 500; }
  .footer { margin-top: 20px; font-size: 12px; color: #bbb; text-align: center; }
</style>
<script>setTimeout(() => location.reload(), 5000);</script>
</head>
<body>
<div class="card">
  <div class="header">
    <div class="dot"></div>
    <div>
      <span class="badge {{ badge_class }}">{{ location }}</span>
      <h1>Auto-Scaled Web App</h1>
    </div>
  </div>
  <p class="server-name">Served by: <strong>{{ hostname }}</strong></p>
  <div class="grid">
    <div class="stat">
      <div class="stat-val">{{ cpu }}%</div>
      <div class="stat-lbl">CPU Usage</div>
      <div class="bar"><div class="bar-fill cpu" style="width:{{ cpu }}%"></div></div>
    </div>
    <div class="stat">
      <div class="stat-val">{{ mem }}%</div>
      <div class="stat-lbl">Memory Usage</div>
      <div class="bar"><div class="bar-fill mem" style="width:{{ mem }}%"></div></div>
    </div>
  </div>
  <div>
    <div class="info-row"><span>Server IP</span><span class="info-val">{{ ip }}</span></div>
    <div class="info-row"><span>Request from</span><span class="info-val">{{ client_ip }}</span></div>
    <div class="info-row"><span>Server time</span><span class="info-val">{{ time }}</span></div>
    <div class="info-row"><span>Platform</span><span class="info-val">{{ platform }}</span></div>
  </div>
  <p class="footer">Refreshes every 5s &nbsp;·&nbsp; VCC Assignment 3 &nbsp;·&nbsp; Cloud Auto-Scaling</p>
</div>
</body>
</html>"""


def is_gcp():
    """Detect if running on GCP by checking metadata server."""
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://metadata.google.internal/computeMetadata/v1/instance/name",
            headers={"Metadata-Flavor": "Google"}
        )
        urllib.request.urlopen(req, timeout=1)
        return True
    except Exception:
        return False


_on_gcp = None


@app.route("/")
def home():
    global _on_gcp
    if _on_gcp is None:
        _on_gcp = is_gcp()
    cpu = round(psutil.cpu_percent(interval=0.5), 1)
    mem = round(psutil.virtual_memory().percent, 1)
    return render_template_string(
        HTML,
        hostname=platform.node(),
        cpu=cpu,
        mem=mem,
        ip=socket.gethostbyname(socket.gethostname()),
        client_ip=request.headers.get("X-Real-IP", request.remote_addr),
        time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        platform=platform.system() + " " + platform.release()[:10],
        location="GCP Cloud Instance" if _on_gcp else "Local VM",
        badge_class="badge-cloud" if _on_gcp else "badge-local",
    )


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
