# VIGIL — Installation Guide

This guide covers installation from source. If you just want to run VIGIL without Python, download the pre-built binaries from the [Releases page](https://github.com/christ20351/VIGIL/releases) and follow the Quick Start in the [README](README.md).

---

## Prerequisites

- Python 3.11+
- `pip` or `uv`
- Network connectivity between monitored machines and the server
- Administrator / root privileges (required for full network metrics)

---

## Installation from Source

### 1. Clone the repository

```bash
git clone https://github.com/christ20351/VIGIL.git
cd VIGIL
git checkout vigil-auth
```

### 2. Automated install (recommended)

**Windows:**
```cmd
install.bat
```

**Linux/Mac:**
```bash
chmod +x install.sh
./install.sh
```

The script will ask whether to install the **Server** or the **Agent**, install dependencies, configure and optionally start the component.

### 3. Manual install

**Server:**
```bash
cd server
pip install -r requirements.txt
# or with uv:
uv pip install -r requirements.txt
```

**Agent:**
```bash
cd agent
pip install -r requirements.txt
# or with uv:
uv pip install -r requirements.txt
```

---

## Starting the Components

### Server

```bash
cd server
python server.py
```

On first launch, an interactive setup menu will appear asking for:
- Listening host and port
- Authentication (enable/disable + secret token)
- Alert thresholds (CPU, RAM, Disk)

Configuration is saved to `server/config.yaml`. To reconfigure later:

```bash
python server.py --reconfigure
```

Optional terminal dashboard mode:
```bash
python server.py --mode terminal
```

### Agent

**Linux (recommended with sudo for full network access):**
```bash
cd agent
sudo python agent.py
```

**Windows (run terminal as Administrator):**
```cmd
cd agent
python agent.py
```

On first launch, the agent will ask for the server IP, port, and update interval. Configuration is saved to `agent/agent_config.json`. To reconfigure:

```bash
python agent.py --reconfigure
```

---

## Configuration

### Server — `server/config.yaml`

| Parameter | Default | Description |
|---|---|---|
| `SERVER_HOST` | `"0.0.0.0"` | Listening interface (`0.0.0.0` = all) |
| `SERVER_PORT` | `5000` | Web server port |
| `ALLOWED_AGENT_IPS` | `[]` | Allowed IPs for agents (empty = all) |
| `ALLOWED_CLIENT_IPS` | `[]` | Allowed IPs for browsers (empty = all) |
| `ENABLE_AUTH` | `false` | Enable session authentication |
| `AUTH_TOKEN` | `"..."` | Secret token (if auth enabled) |
| `TIMEOUT` | `60` | Seconds before marking agent offline |
| `CPU_ALERT_THRESHOLD` | `90` | CPU (%) alert threshold |
| `CPU_ALERT_DURATION` | `25` | Seconds above CPU threshold to trigger alert |
| `RAM_ALERT_THRESHOLD` | `95` | RAM (%) alert threshold |
| `DISK_ALERT_THRESHOLD` | `90` | Disk (%) alert threshold |
| `PROCESS_LIMIT` | `100` | Max processes reported per agent |
| `NETWORK_CONN_LIMIT` | `100` | Max network connections reported per agent |

You can also edit these settings live from the **Settings** tab in the web interface — changes are saved immediately with an automatic backup.

### Agent — `agent/agent_config.json`

| Parameter | Default | Description |
|---|---|---|
| `SERVER_IP` | `"192.168.1.10"` | Central server IP or hostname |
| `SERVER_PORT` | `5000` | Central server port |
| `UPDATE_INTERVAL` | `1` | Metrics send interval (seconds) |
| `ENABLE_AUTH` | `false` | Enable auth token |
| `AUTH_TOKEN` | `null` | Token (must match server `AUTH_TOKEN`) |

---

## Ports

| Component | Port | Protocol | Description |
|---|---|---|---|
| Server | `5000` (configurable) | TCP | Web dashboard + WebSocket |
| Agent | `8080` | TCP | Fallback ping endpoint |

Open the server port on your firewall:

```bash
# Linux
sudo ufw allow 5000/tcp

# Windows (PowerShell as Administrator)
netsh advfirewall firewall add rule name="VIGIL Server" dir=in action=allow protocol=TCP localport=5000
```

---

## Verifying the Installation

1. Start the server — open `http://localhost:5000` in your browser
2. Start one or more agents pointing to the server IP
3. Agents appear in the dashboard within a few seconds
4. Click **Details** on any agent card to view real-time graphs

---

## Troubleshooting

**Agent not appearing in dashboard**
- Check that `SERVER_IP` in `agent_config.json` matches the server's actual IP
- Verify port 5000 is open on the server firewall
- Make sure the server is running before starting the agent

**Permission errors on Linux**
- Run the agent with `sudo` for full network and process access

**Port already in use**
- Change `SERVER_PORT` in `server/config.yaml` and restart the server

**Reset server configuration**
- Use the **Reset** button in the Settings tab (web interface)
- Or manually replace `config.yaml` with `config.yaml.bak`