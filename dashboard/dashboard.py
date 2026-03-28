#!/usr/bin/env python3
"""
dashboard/dashboard.py  –  Real-time monitoring + logging dashboard.
Access at http://<your-vm-ip>:8080
"""
import json, os, datetime
from collections import deque
from flask import Flask, jsonify, render_template_string
import psutil

app = Flask(__name__)

STATE_FILE = "/home/server/vcc-assignment-3/state.json"
LOG_FILE   = "/home/server/vcc-assignment-3/monitor.log"

# In-memory history for charts (last 60 readings = 30 min at 30s intervals)
cpu_hist  = deque(maxlen=60)
mem_hist  = deque(maxlen=60)
time_hist = deque(maxlen=60)

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VCC Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #f0f4f8; color: #333; }
  .topbar { background: #1a1a2e; color: white; padding: 14px 28px; display: flex;
            align-items: center; justify-content: space-between; }
  .topbar h1 { font-size: 18px; font-weight: 600; }
  .topbar .meta { font-size: 12px; color: #aaa; }
  .live-dot { width: 8px; height: 8px; border-radius: 50%; background: #34a853;
              display: inline-block; margin-right: 6px; animation: pulse 1.5s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
  .main { max-width: 1200px; margin: 0 auto; padding: 24px; }
  .section-title { font-size: 13px; font-weight: 600; text-transform: uppercase;
                   letter-spacing: 1px; color: #888; margin: 24px 0 12px; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; }
  .card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
  .card-val { font-size: 32px; font-weight: 700; color: #1a73e8; }
  .card-val.green { color: #34a853; }
  .card-val.amber { color: #f9ab00; }
  .card-val.red   { color: #ea4335; }
  .card-lbl { font-size: 11px; color: #888; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
  .bar { height: 6px; border-radius: 3px; background: #e8eaed; margin-top: 12px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 3px; transition: width 0.4s; }
  .chart-wrap { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 16px; }
  .chart-wrap canvas { max-height: 220px; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; padding: 10px 12px; font-size: 11px; text-transform: uppercase;
       letter-spacing: 0.5px; color: #888; border-bottom: 1px solid #eee; }
  td { padding: 10px 12px; border-bottom: 1px solid #f5f5f5; }
  tr:last-child td { border-bottom: none; }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 6px; }
  .status-running { background: #34a853; }
  .status-unknown { background: #aaa; }
  .log-box { background: #1a1a2e; color: #a8d8a8; border-radius: 12px; padding: 16px;
             font-family: 'Courier New', monospace; font-size: 12px; line-height: 1.6;
             max-height: 340px; overflow-y: auto; }
  .log-warn  { color: #f9ab00; }
  .log-error { color: #ea4335; }
  .log-info  { color: #a8d8a8; }
  .empty-row { text-align: center; color: #bbb; padding: 24px; }
  @media (max-width: 700px) { .grid2 { grid-template-columns: 1fr; } }
</style>
</head>
<body>

<div class="topbar">
  <h1><span class="live-dot"></span>VCC Auto-Scale Dashboard</h1>
  <span class="meta" id="last-update">Connecting...</span>
</div>

<div class="main">

  <div class="section-title">Local VM overview</div>
  <div class="cards">
    <div class="card">
      <div class="card-val" id="cpu-val">—</div>
      <div class="card-lbl">CPU Usage</div>
      <div class="bar"><div class="bar-fill" id="cpu-bar" style="background:#1a73e8;width:0%"></div></div>
    </div>
    <div class="card">
      <div class="card-val green" id="mem-val">—</div>
      <div class="card-lbl">Memory Usage</div>
      <div class="bar"><div class="bar-fill" id="mem-bar" style="background:#34a853;width:0%"></div></div>
    </div>
    <div class="card">
      <div class="card-val" id="inst-val">0</div>
      <div class="card-lbl">GCP instances</div>
    </div>
    <div class="card">
      <div class="card-val" id="scale-val">Idle</div>
      <div class="card-lbl">Scale status</div>
    </div>
  </div>

  <div class="section-title">Resource history</div>
  <div class="grid2">
    <div class="chart-wrap">
      <canvas id="cpu-chart"></canvas>
    </div>
    <div class="chart-wrap">
      <canvas id="mem-chart"></canvas>
    </div>
  </div>

  <div class="section-title">GCP instances</div>
  <div class="chart-wrap">
    <table>
      <thead>
        <tr><th>Instance</th><th>IP address</th><th>CPU</th><th>Status</th></tr>
      </thead>
      <tbody id="inst-table">
        <tr><td colspan="4" class="empty-row">No cloud instances running</td></tr>
      </tbody>
    </table>
  </div>

  <div class="section-title">Monitor logs</div>
  <div class="log-box" id="log-box">Loading logs...</div>

</div>

<script>
const mkChart = (id, label, color) => new Chart(document.getElementById(id), {
  type: 'line',
  data: { labels: [], datasets: [{ label, data: [], borderColor: color, backgroundColor: color+'22',
          borderWidth: 2, pointRadius: 0, fill: true, tension: 0.4 }] },
  options: { animation: false, responsive: true, maintainAspectRatio: true,
    plugins: { legend: { display: true, labels: { font: { size: 11 } } } },
    scales: {
      x: { ticks: { font: { size: 10 }, maxTicksLimit: 8 }, grid: { display: false } },
      y: { min: 0, max: 100, ticks: { callback: v => v + '%', font: { size: 10 } } }
    }
  }
});

const cpuChart = mkChart('cpu-chart', 'CPU %', '#1a73e8');
const memChart = mkChart('mem-chart', 'Memory %', '#34a853');

function colorClass(v) {
  if (v >= 75) return 'red';
  if (v >= 50) return 'amber';
  return 'green';
}

async function fetchStats() {
  try {
    const r = await fetch('/api/stats');
    const d = await r.json();

    document.getElementById('cpu-val').textContent = d.cpu + '%';
    document.getElementById('cpu-val').className = 'card-val ' + colorClass(d.cpu);
    document.getElementById('cpu-bar').style.width = d.cpu + '%';
    document.getElementById('mem-val').textContent = d.mem + '%';
    document.getElementById('mem-val').className = 'card-val ' + colorClass(d.mem);
    document.getElementById('mem-bar').style.width = d.mem + '%';
    document.getElementById('last-update').textContent = 'Updated ' + new Date().toLocaleTimeString();

    cpuChart.data.labels = d.time_history;
    cpuChart.data.datasets[0].data = d.cpu_history;
    cpuChart.update('none');
    memChart.data.labels = d.time_history;
    memChart.data.datasets[0].data = d.mem_history;
    memChart.update('none');
  } catch(e) { console.error('stats:', e); }
}

async function fetchInstances() {
  try {
    const r = await fetch('/api/instances');
    const d = await r.json();
    document.getElementById('inst-val').textContent = d.instance_count || 0;
    document.getElementById('scale-val').textContent = d.scaled_out ? 'Scaled out' : 'Idle';
    document.getElementById('scale-val').className = 'card-val ' + (d.scaled_out ? 'amber' : 'green');

    const tbody = document.getElementById('inst-table');
    if (!d.instances || d.instances.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="empty-row">No cloud instances running</td></tr>';
    } else {
      tbody.innerHTML = d.instances.map(inst => `
        <tr>
          <td><span class="status-dot ${inst.status === 'RUNNING' ? 'status-running' : 'status-unknown'}"></span>${inst.name}</td>
          <td>${inst.ip || '—'}</td>
          <td>${inst.cpu != null ? inst.cpu + '%' : '—'}</td>
          <td>${inst.status || 'unknown'}</td>
        </tr>
      `).join('');
    }
  } catch(e) { console.error('instances:', e); }
}

async function fetchLogs() {
  try {
    const r = await fetch('/api/logs');
    const d = await r.json();
    const box = document.getElementById('log-box');
    box.innerHTML = d.lines.map(l => {
      const cls = l.includes('[WARNING]') || l.includes('[ERROR]')
        ? (l.includes('[ERROR]') ? 'log-error' : 'log-warn')
        : 'log-info';
      return `<div class="${cls}">${l.replace(/</g,'&lt;').trimEnd()}</div>`;
    }).join('');
    box.scrollTop = box.scrollHeight;
  } catch(e) { console.error('logs:', e); }
}

function refresh() {
  fetchStats();
  fetchInstances();
  fetchLogs();
}

refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/stats")
def api_stats():
    cpu = round(psutil.cpu_percent(interval=0.5), 1)
    mem = round(psutil.virtual_memory().percent, 1)
    now = datetime.datetime.now().strftime("%H:%M:%S")
    cpu_hist.append(cpu)
    mem_hist.append(mem)
    time_hist.append(now)
    return jsonify({
        "cpu": cpu, "mem": mem, "time": now,
        "cpu_history":  list(cpu_hist),
        "mem_history":  list(mem_hist),
        "time_history": list(time_hist),
    })


@app.route("/api/instances")
def api_instances():
    try:
        with open(STATE_FILE) as f:
            return jsonify(json.load(f))
    except Exception:
        return jsonify({"instances": [], "instance_count": 0, "scaled_out": False})


@app.route("/api/logs")
def api_logs():
    try:
        with open(LOG_FILE) as f:
            lines = f.readlines()
        return jsonify({"lines": lines[-80:]})
    except Exception:
        return jsonify({"lines": ["Log file not found"]})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
