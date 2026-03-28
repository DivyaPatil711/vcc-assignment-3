"""
sample_app.py – Sample application deployed on GCP during auto-scale.
Exposes a simple web server to demonstrate the deployment is live.
"""

from flask import Flask, jsonify
import platform, psutil, datetime

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <html>
    <head><title>Auto-Scaled App on GCP</title></head>
    <body style="font-family:Arial;max-width:700px;margin:60px auto;text-align:center;">
      <h1>✅ Auto-Scaled App Running on GCP!</h1>
      <p>This VM was automatically provisioned when the local VM exceeded 75% resource usage.</p>
      <p>Visit <a href="/status">/status</a> for system info.</p>
    </body>
    </html>
    """

@app.route("/status")
def status():
    return jsonify({
        "hostname"   : platform.node(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_used": f"{psutil.virtual_memory().percent:.1f}%",
        "uptime"     : str(datetime.datetime.now()),
        "platform"   : platform.system(),
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=False)
