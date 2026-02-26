# 🖥️ VIGIL — Centralized Monitoring System v2.0

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.0-orange)](CHANGELOG.md)

A powerful and lightweight real-time monitoring system to supervise multiple computers from a central web interface — no cloud, no subscription, fully self-hosted.

![Dashboard](docs/screenshots/dashboard.png)

---

## 🎯 Architecture

```
┌─────────────┐        ┌─────────────────┐        ┌─────────────┐
│   Agent     │──WS──▶ │  Central Server  │ ◀──WS──│   Agent     │
│  (PC 1)     │        │   (FastAPI)      │        │  (PC 2)     │
└─────────────┘        └─────────────────┘        └─────────────┘
                                │
                                ▼
                         Web Interface
                       http://SERVER_IP:5000
```

- **Agent** : installed on each machine to monitor. Collects metrics and sends them to the server via WebSocket every second.
- **Server** : central hub that receives all metrics, stores history in SQLite, and serves the web dashboard.
- **Dashboard** : real-time web interface accessible from any browser on the network.

---

## ✨ Features

### 📊 Real-time Monitoring
- CPU, RAM, Disk usage with live graphs
- Network traffic: upload/download speed
- Top 30 processes by CPU usage (PID, name, CPU%, RAM%, state, user)
- Active network connections (TCP/UDP, local/remote IPs, states)
- Network interfaces: IPv4, IPv6, speed, active/inactive state

### 🖥️ Modern Interface
- Responsive web dashboard (Chart.js)
- Distinctive PC icons with online/offline status badges
- History tab: visualize last 24h+ of metrics
- Notifications panel: alerts organized by agent and day
- Activity sidebar: browse history per agent (1h / 4h / 24h / 7d)
- Smooth animations and transitions

### 🔔 Configurable Alerts
- CPU alert with duration threshold (e.g. CPU > 90% for more than 25s)
- Instant RAM and Disk alerts
- Offline agent detection with red badge and notification

### 🔐 Optional Authentication
- Token-based session authentication
- Login page with first-run account creation
- Logout button in dashboard topbar

### ⚙️ Settings
- Edit all server parameters from the web interface
- Automatic backup before each save
- One-click reset to previous configuration

---

## 🚀 Quick Start

### Option 1 — Pre-built Binaries (Recommended, no Python required)

Download the latest release from the [Releases page](https://github.com/christ20351/VIGIL/releases).

| File | OS | Component |
|---|---|---|
| `vigil-server-windows.zip` | Windows | Central Server |
| `vigil-agent-windows.zip` | Windows | Monitoring Agent |
| `vigil-server-linux.tar.gz` | Linux | Central Server |
| `vigil-agent-linux.tar.gz` | Linux | Monitoring Agent |

**Server setup:**
1. Extract `vigil-server-*` to a folder
2. Run `vigil-server.exe` (Windows) or `./vigil-server` (Linux) **as Administrator**
3. An interactive setup menu appears on first launch — configure host, port, auth, and alert thresholds
4. Open your browser at `http://localhost:5000` (or the configured port)

**Agent setup:**
1. Extract `vigil-agent-*` to a folder
2. Run `vigil-agent.exe` (Windows) or `./vigil-agent` (Linux) **as Administrator**
3. Enter the server IP and port — configuration is saved to `agent_config.json`
4. The agent connects automatically and appears in the dashboard

> ⚠️ **Windows**: if SmartScreen blocks the exe → "More info" → "Run anyway"
> ⚠️ **Linux**: use `sudo ./vigil-agent` for full network access

---

### Option 2 — From Source (requires Python 3.11+)

```bash
git clone https://github.com/christ20351/VIGIL.git
cd VIGIL
```

**Windows:**
```cmd
install.bat
```

**Linux/Mac:**
```bash
chmod +x install.sh
./install.sh
```

The install script will:
- Ask whether to install the **Server** or the **Agent**
- Install Python dependencies automatically
- Create a default `config.yaml`
- Ask for basic configuration (host, port, auth)
- Optionally start the component immediately

**Manual start after installation:**

```bash
# Server
cd server
python server.py

# Agent (Linux)
cd agent
sudo python agent.py

# Agent (Windows — run as Administrator)
cd agent
python agent.py
```

---

## 🔧 Configuration

### Server — `config.yaml`

Generated automatically on first launch next to the executable (or in `server/` when running from source). Edit it manually or use the **Settings** tab in the web interface.

| Parameter | Default | Description |
|---|---|---|
| `SERVER_HOST` | `"0.0.0.0"` | Listening interface (`0.0.0.0` = all) |
| `SERVER_PORT` | `5000` | Web server port |
| `ALLOWED_AGENT_IPS` | `[]` | IPs allowed for agents (empty = all) |
| `ALLOWED_CLIENT_IPS` | `[]` | IPs allowed for browsers (empty = all) |
| `ENABLE_AUTH` | `false` | Enable token authentication |
| `AUTH_TOKEN` | `"..."` | Secret token (if `ENABLE_AUTH = true`) |
| `TIMEOUT` | `60` | Seconds before marking an agent offline |
| `CPU_ALERT_THRESHOLD` | `90` | CPU (%) to trigger alert |
| `CPU_ALERT_DURATION` | `25` | Duration in seconds above CPU threshold |
| `RAM_ALERT_THRESHOLD` | `95` | RAM (%) to trigger instant alert |
| `DISK_ALERT_THRESHOLD` | `90` | Disk (%) to trigger instant alert |
| `PROCESS_LIMIT` | `100` | Max processes reported per agent |
| `NETWORK_CONN_LIMIT` | `100` | Max network connections reported per agent |

> To force reconfiguration via terminal: `vigil-server.exe --reconfigure`

### Agent — `agent_config.json`

Created automatically after the interactive setup on first launch, saved next to the executable.

| Parameter | Default | Description |
|---|---|---|
| `SERVER_IP` | `"192.168.1.10"` | Central server IP or hostname |
| `SERVER_PORT` | `5000` | Central server port |
| `UPDATE_INTERVAL` | `1` | Metrics send interval (seconds) |
| `ENABLE_AUTH` | `false` | Enable auth token |
| `AUTH_TOKEN` | `null` | Token (must match server token) |

> To reconfigure: `vigil-agent.exe --reconfigure`

---

## 📁 File Structure (binaries)

After extracting the release archives, your folders will look like:

```
vigil-server/
├── vigil-server.exe       ← or vigil-server on Linux
├── config.yaml            ← created on first launch
├── config.yaml.bak        ← automatic backup before each save
├── users.yaml             ← user accounts (if auth enabled)
├── metrics.db             ← SQLite history database
├── static/
└── templates/

vigil-agent/
├── vigil-agent.exe        ← or vigil-agent on Linux
└── agent_config.json      ← created after first setup
```

---

## 🌐 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Web dashboard |
| `GET` | `/health` | Server health check |
| `GET` | `/api/computers` | List all agents and their current metrics |
| `GET` | `/api/history/{hostname}?hours=24` | Metric history for a specific agent |
| `GET` | `/api/notifications` | List all alerts |
| `GET` | `/api/settings` | Read current server configuration |
| `POST` | `/api/settings` | Update server configuration |
| `POST` | `/api/settings/reset` | Restore configuration from backup |
| `WS` | `/ws` | WebSocket for web clients (browser) |
| `WS` | `/ws/agent` | WebSocket for agents |

---

## 🏢 Deployment Guide

### Example: 1 server + 20 PCs

**Step 1 — Central Server**
1. Choose a machine that stays on 24/7
2. Run `vigil-server.exe` and complete the setup
3. Note the displayed IP (e.g. `192.168.1.10`)
4. Open the firewall port:
   ```bash
   sudo ufw allow 5000/tcp   # Linux
   # or Windows Firewall → New inbound rule → Port 5000
   ```
5. Access `http://192.168.1.10:5000`

**Step 2 — Agents**

On each PC to monitor:
1. Copy and extract `vigil-agent-windows.zip`
2. Run `vigil-agent.exe` as Administrator
3. Enter the server IP: `192.168.1.10`
4. The PC appears immediately in the dashboard

**Step 3 — Verification**
- Open `http://192.168.1.10:5000`
- All PCs appear with their icons
- Click **Details** on any card to view graphs and processes

---

## 📋 Requirements

### Binaries (no installation needed)
- Windows 10/11 or Linux (x86_64)
- Network connectivity between machines
- Administrator/root privileges

### From source
- Python 3.11+
- See `server/requirements.txt` and `agent/requirements.txt`

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first.

```
git clone https://github.com/christ20351/VIGIL.git
git checkout -b feature/your-feature
git commit -m "feat: your feature"
git push origin feature/your-feature
```