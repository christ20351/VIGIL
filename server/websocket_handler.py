"""
WebSocket support pour les mises à jour en temps réel
Gère deux types de WebSocket:
1. /ws         - Pour les clients web (navigateur)
2. /ws/agent   - Pour les agents qui envoient les données

Optimisations:
- Un seul task de diffusion diffuse un snapshot (allégé par défaut) à tous
  les navigateurs, au lieu d'un snapshot complet construit par client.
- Les agents peuvent envoyer des payloads partiels (sections lourdes omises
  quand elles n'ont pas changé) : le serveur les recolle sur les dernières
  valeurs connues avant stockage/diffusion.
- Authentification stricte des agents dès lors qu'un token est configuré.
"""

import asyncio
import hmac
import json
import time
from datetime import datetime

from config import ALLOWED_AGENT_IPS, ALLOWED_CLIENT_IPS

# stockage historique
try:
    from db.storage import insert_metric, insert_notification
except ImportError:
    insert_metric = lambda *args, **kwargs: None
    insert_notification = lambda *args, **kwargs: None

from fastapi import WebSocket, WebSocketDisconnect

# événement loop principal (capturé à l'initialisation FastAPI)
main_loop = None

# journalisation console des métriques agents (1 ligne sur N pour éviter
# le spam — les services Windows/Linux n'ont pas besoin d'un log/seconde)
AGENT_LOG_EVERY = 10


def set_main_loop(loop):
    global main_loop
    main_loop = loop


class ClientConnectionManager:
    """Gère les connexions WebSocket des clients web"""

    def __init__(self):
        self.active_connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"✓ Client web connecté (total: {len(self.active_connections)})")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"✗ Client web déconnecté (total: {len(self.active_connections)})")

    async def broadcast(self, message: dict):
        """Envoie un message à tous les clients connectés"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


class AgentConnectionManager:
    """Gère les connexions WebSocket des agents"""

    def __init__(self):
        self.agent_connections = {}  # hostname -> websocket
        self.last_seen = {}          # hostname -> time.monotonic()

    async def connect(self, websocket: WebSocket, hostname: str):
        old = self.agent_connections.get(hostname)
        if old is not None:
            try:
                await old.close()
            except Exception:
                pass
        self.agent_connections[hostname] = websocket
        self.last_seen[hostname] = time.monotonic()
        print(
            f"✓ Agent connecté: {hostname} (total agents: {len(self.agent_connections)})"
        )

    def disconnect(self, hostname: str):
        if hostname in self.agent_connections:
            del self.agent_connections[hostname]
            print(
                f"✗ Agent déconnecté: {hostname} (total agents: {len(self.agent_connections)})"
            )

    def touch(self, hostname: str):
        self.last_seen[hostname] = time.monotonic()

    def seconds_since_last_message(self, hostname: str):
        last = self.last_seen.get(hostname)
        if last is None:
            return None
        return time.monotonic() - last

    async def get_agent_socket(self, hostname: str):
        return self.agent_connections.get(hostname)

    def get_all_agents(self):
        return list(self.agent_connections.keys())


# Managers globaux
client_manager = ClientConnectionManager()
agent_manager = AgentConnectionManager()

# état pour la surveillance des seuils par agent
_threshold_state = {}

# ── Canal de commandes à distance (dashboard / Vili → agents) ──
# command_id -> asyncio.Future résolu par le message "exec_result" de l'agent
_pending_commands: dict = {}


async def send_command_to_agent(
    hostname: str, command: str, timeout: int = 60
) -> dict:
    """
    Envoie une commande système à exécuter sur l'agent `hostname` et
    attend son résultat. Retourne {ok, stdout, stderr, exit_code} ou
    {ok: False, error}.
    """
    websocket = agent_manager.agent_connections.get(hostname)
    if websocket is None:
        return {"ok": False, "error": f"Agent '{hostname}' hors ligne ou non connecté."}

    import uuid

    cmd_id = uuid.uuid4().hex[:16]
    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()
    _pending_commands[cmd_id] = fut

    try:
        await websocket.send_json(
            {"type": "exec", "id": cmd_id, "command": command, "timeout": timeout}
        )
    except Exception as e:
        _pending_commands.pop(cmd_id, None)
        return {"ok": False, "error": f"Échec d'envoi à l'agent : {e}"}

    try:
        result = await asyncio.wait_for(fut, timeout=timeout + 5)
        return {"ok": True, **result}
    except asyncio.TimeoutError:
        return {"ok": False, "error": f"L'agent n'a pas répondu en {timeout}s."}
    finally:
        _pending_commands.pop(cmd_id, None)


def notify_dashboard_sync(hostname: str, message: str, severity: str = "info"):
    """
    Notifie le dashboard administrateur depuis n'importe quel thread
    (utilisé par la boucle autonome de Vili) : persiste en base et
    diffuse l'alerte aux navigateurs connectés.
    """
    from datetime import datetime as _dt

    try:
        insert_notification(hostname, message, severity)
    except Exception:
        pass
    # dispatch vers les canaux sortants (webhook / email)
    try:
        import notify_out

        notify_out.dispatch_alert(hostname, message, severity)
    except Exception:
        pass
    payload = {
        "type": "alert",
        "hostname": hostname,
        "message": message,
        "severity": severity,
        "timestamp": _dt.now().isoformat(),
    }
    if main_loop is not None:
        try:
            asyncio.run_coroutine_threadsafe(
                client_manager.broadcast(payload), main_loop
            )
        except Exception:
            pass


def broadcast_approval_request(approval: dict):
    """
    Diffuse une demande d'autorisation Vili (exécuter une commande ?)
    aux navigateurs connectés : le front affiche la carte Oui / Non.
    Appelable depuis n'importe quel thread.
    """
    if main_loop is None:
        return
    payload = {
        "type": "approval_request",
        "id": approval.get("id"),
        "hostname": approval.get("hostname"),
        "command": approval.get("command"),
        "reason": approval.get("reason") or "",
        "timestamp": approval.get("ts"),
    }
    try:
        asyncio.run_coroutine_threadsafe(
            client_manager.broadcast(payload), main_loop
        )
    except Exception:
        pass


def broadcast_approval_done(approval: dict):
    """Informe les navigateurs qu'une demande a été tranchée/exécutée."""
    if main_loop is None:
        return
    payload = {
        "type": "approval_done",
        "id": approval.get("id"),
        "status": approval.get("status"),
        "hostname": approval.get("hostname"),
        "command": approval.get("command"),
    }
    try:
        asyncio.run_coroutine_threadsafe(
            client_manager.broadcast(payload), main_loop
        )
    except Exception:
        pass


# ================================================================
#  SNAPSHOT PUBLIC (diffusion aux navigateurs)
# ================================================================

# clés retirées du flux seconde par seconde (récupérables à la demande
# via /api/computers/{hostname}/detail)
_LIGHT_STRIP_KEYS = ("processes", "interfaces")
_SMART_DISK_KEYS = (
    "disk", "health", "temperature", "power_on_hours",
    "reallocated_sectors", "model", "protocol", "available",
)


def _slim_smart(smart: dict) -> dict:
    if not isinstance(smart, dict):
        return {}
    out = {
        "available": smart.get("available", False),
        "alerts": smart.get("alerts", []),
        "disks_count": smart.get("disks_count"),
    }
    disks = []
    for d in smart.get("disks", []) or []:
        if isinstance(d, dict):
            disks.append({k: d.get(k) for k in _SMART_DISK_KEYS})
    out["disks"] = disks
    return out


def public_snapshot(computers_data: dict, full_detail: bool = False) -> dict:
    """
    Construit la vue diffusée aux navigateurs.
    Par défaut (BROADCAST_FULL_DETAIL=False) les sections volumineuses
    (processus, interfaces, listes de connexions) sont retirées : elles
    restent disponibles via l'API détail pour les vues qui en ont besoin.
    """
    try:
        import config as _config

        full_detail = full_detail or bool(getattr(_config, "BROADCAST_FULL_DETAIL", False))
    except Exception:
        pass
    if full_detail:
        return computers_data

    light = {}
    for host, data in computers_data.items():
        if not isinstance(data, dict):
            continue
        d = {k: v for k, v in data.items() if k not in _LIGHT_STRIP_KEYS}
        protocols = d.get("protocols")
        if isinstance(protocols, dict):
            p = dict(protocols)
            tcp = p.get("tcp")
            if isinstance(tcp, dict):
                p["tcp"] = {k: v for k, v in tcp.items() if k != "connections"}
            udp = p.get("udp")
            if isinstance(udp, dict):
                p["udp"] = {k: v for k, v in udp.items() if k != "connections"}
            p.pop("listening_ports", None)
            d["protocols"] = p
        if "smart" in d:
            d["smart"] = _slim_smart(d.get("smart") or {})
        light[host] = d
    return light


# ================================================================
#  VÉRIFICATION DES SEUILS (CPU / RAM / DISK / SMART)
# ================================================================


def _check_thresholds(hostname: str, agent_data: dict, smart_payload: dict) -> list:
    """
    Contrôle les valeurs contre les seuils configurés.
    Retourne une liste de tuples (message, severity).
    """
    now = time.time()
    state = _threshold_state.setdefault(hostname, {})
    alerts = []

    from config import (
        CPU_ALERT_DURATION,
        CPU_ALERT_THRESHOLD,
        DISK_ALERT_THRESHOLD,
        RAM_ALERT_THRESHOLD,
    )

    # ── CPU ───────────────────────────────────────────────────────
    cpu = agent_data.get("cpu_percent", 0)
    if cpu >= CPU_ALERT_THRESHOLD:
        if "cpu" not in state:
            state["cpu"] = now
        elif now - state["cpu"] >= CPU_ALERT_DURATION:
            alerts.append((f"CPU élevé ({cpu:.1f}%)", "warning"))
            state["cpu"] = now
    else:
        state.pop("cpu", None)

    # ── RAM ───────────────────────────────────────────────────────
    ram = agent_data.get("memory", {}).get("percent", 0)
    if ram > RAM_ALERT_THRESHOLD:
        if now - state.get("ram_alert", 0) >= 300:  # re-alerte max toutes les 5 min
            alerts.append((f"RAM critique ({ram:.1f}%)", "error"))
            state["ram_alert"] = now

    # ── DISQUE ────────────────────────────────────────────────────
    disk = agent_data.get("disk", {}).get("percent", 0)
    if disk >= DISK_ALERT_THRESHOLD:
        if now - state.get("disk_alert", 0) >= 300:  # re-alerte max toutes les 5 min
            alerts.append((f"Disque plein ({disk:.1f}%)", "error"))
            state["disk_alert"] = now

    # ── S.M.A.R.T. ────────────────────────────────────────────────
    if smart_payload and smart_payload.get("available"):
        for alert in smart_payload.get("alerts", []):
            disk_name = alert.get("disk", "?")
            alert_type = alert.get("type", "unknown")
            level = alert.get("level", "WARNING")
            message = alert.get("message", "")

            # Clé unique pour éviter le spam (re-alerte toutes les 5 min)
            alert_key = f"smart_{disk_name}_{alert_type}"
            if alert_key not in state or now - state[alert_key] >= 300:
                severity = "error" if level == "CRITICAL" else "warning"
                alerts.append((message, severity))
                state[alert_key] = now

    return alerts


# ================================================================
#  ENDPOINT CLIENTS WEB
# ================================================================


async def web_client_endpoint(websocket: WebSocket, computers_data):
    """Endpoint WebSocket pour les clients web (navigateurs)"""
    client_ip = websocket.client.host
    if ALLOWED_CLIENT_IPS and client_ip not in ALLOWED_CLIENT_IPS:
        try:
            import security_events

            security_events.log_blocked_once(
                f"web:{client_ip}",
                f"Client web refusé : {client_ip} hors liste blanche "
                "ALLOWED_CLIENT_IPS",
            )
        except Exception:
            pass
        await websocket.close(code=1008, reason="IP not allowed")
        return

    await client_manager.connect(websocket)
    try:
        # Envoi initial de l'état complet
        await websocket.send_json(
            {
                "type": "update",
                "data": public_snapshot(computers_data),
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Les mises à jour périodiques sont poussées par le broadcaster
        # global (un seul snapshot construit par tick pour tous les
        # clients). On attend ici la fermeture du socket.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        client_manager.disconnect(websocket)
    except Exception:
        client_manager.disconnect(websocket)


async def _broadcast_loop(computers_data):
    """Diffuse le snapshot (allégé par défaut) à tous les navigateurs chaque seconde."""
    while True:
        try:
            if client_manager.active_connections:
                await client_manager.broadcast(
                    {
                        "type": "update",
                        "data": public_snapshot(computers_data),
                        "timestamp": datetime.now().isoformat(),
                    }
                )
        except Exception as e:
            print(f"⚠️  Erreur boucle de diffusion: {e}")
        await asyncio.sleep(1)


# ================================================================
#  ENDPOINT AGENTS
# ================================================================


# sections lourdes que l'agent peut omettre quand inchangées :
# le serveur recolle la dernière valeur connue
_MERGE_KEYS = ("processes", "interfaces", "protocols", "smart")


async def agent_endpoint(websocket: WebSocket, computers_data):
    """Endpoint WebSocket pour les agents qui envoient les données"""
    client_ip = websocket.client.host
    if ALLOWED_AGENT_IPS and client_ip not in ALLOWED_AGENT_IPS:
        try:
            import security_events

            security_events.log_blocked_once(
                f"agent:{client_ip}",
                f"Agent refusé : {client_ip} hors liste blanche "
                "ALLOWED_AGENT_IPS",
            )
        except Exception:
            pass
        await websocket.close(code=1008, reason="IP not allowed")
        return

    hostname = None
    agent_ip = client_ip
    msg_count = 0

    try:
        await websocket.accept()
        print(f"-> agent connection accepted from {client_ip}")

        # ── Message d'enregistrement initial ──────────────────────
        try:
            initial_msg = await websocket.receive_json()
        except WebSocketDisconnect:
            print(
                f"! WebSocketDisconnect while waiting initial register from {client_ip}"
            )
            return
        except Exception as e:
            print(f"! Exception while receiving initial register from {client_ip}: {e}")
            try:
                await websocket.close(code=1011, reason="receive error")
            except Exception:
                pass
            return

        # ── Authentification ──────────────────────────────────────
        try:
            from config import AUTH_TOKEN, ENABLE_AUTH
        except ImportError:
            ENABLE_AUTH = False
            AUTH_TOKEN = None

        if not isinstance(initial_msg, dict):
            print(f"✗ Message d'enregistrement invalide depuis {client_ip}")
            try:
                await websocket.close(code=1002, reason="Invalid register payload")
            except Exception:
                pass
            return

        if ENABLE_AUTH and AUTH_TOKEN:
            token = initial_msg.get("auth_token")
            if not token or not hmac.compare_digest(str(token), str(AUTH_TOKEN)):
                print(
                    f"✗ Authentification agent refusée depuis {client_ip} "
                    f"(token absent ou invalide)"
                )
                try:
                    import security_events

                    security_events.log_security_event(
                        "agent_auth_failed",
                        f"Connexion agent refusée depuis {client_ip}"
                        f" (hostname déclaré : {initial_msg.get('hostname') or '?'})",
                        severity="critical",
                        source=client_ip,
                    )
                except Exception:
                    pass
                await websocket.close(code=1008, reason="Invalid token")
                return

        # ── Extraction hostname ────────────────────────────────────
        if initial_msg.get("type") == "register":
            hostname = initial_msg.get("hostname")
            agent_ip = initial_msg.get("local_ip") or client_ip
        else:
            hostname = initial_msg.get("hostname") or initial_msg.get("host")
            agent_ip = initial_msg.get("local_ip") or client_ip

        if not hostname:
            print(
                f"✗ No hostname provided by agent from {client_ip}; closing connection"
            )
            try:
                await websocket.close(code=1000, reason="No hostname provided")
            except Exception:
                pass
            return

        await agent_manager.connect(websocket, hostname)
        is_first = hostname not in computers_data

        # ── Boucle de réception des métriques ─────────────────────
        while True:
            try:
                message = await websocket.receive_json()
            except WebSocketDisconnect:
                print(
                    f"! WebSocketDisconnect while receiving from {hostname} ({client_ip})"
                )
                break
            except Exception as e:
                print(
                    f"! Exception while receiving JSON from {hostname} ({client_ip}): {e}"
                )
                break

            if message.get("type") == "exec_result":
                # Résultat d'une commande distante exécutée par l'agent
                cmd_id = message.get("id")
                fut = _pending_commands.get(cmd_id)
                if fut is not None and not fut.done():
                    fut.set_result(
                        {
                            "stdout": message.get("stdout", ""),
                            "stderr": message.get("stderr", ""),
                            "exit_code": message.get("exit_code"),
                        }
                    )
                continue

            if message.get("type") == "inventory":
                # Inventaire matériel/logiciel remonté par l'agent
                try:
                    from db.storage import upsert_inventory

                    inv_data = message.get("data") or {}
                    await asyncio.to_thread(upsert_inventory, hostname, inv_data)
                    print(f"📦 Inventaire reçu de {hostname}")
                except Exception as e:
                    print(f"⚠️  Erreur stockage inventaire {hostname}: {e}")
                continue

            if message.get("type") == "metrics":
                agent_manager.touch(hostname)
                agent_data = message.get("data", {})
                agent_data["agent_ip"] = agent_ip
                agent_data["last_seen"] = datetime.now().isoformat()
                agent_data["offline"] = False
                agent_data.pop("offline_since", None)

                # ── Payload S.M.A.R.T. (champ du message) ──────────
                message_smart = message.get("smart")
                if isinstance(message_smart, dict) and message_smart:
                    agent_data["smart"] = message_smart

                # ── Fusion des sections lourdes omises par l'agent ─
                prev = computers_data.get(hostname) or {}
                for key in _MERGE_KEYS:
                    if key not in agent_data and key in prev:
                        agent_data[key] = prev[key]

                # ── Récupération payload SMART (fusionné) ───────────
                smart_payload = agent_data.get("smart", {})
                if not isinstance(smart_payload, dict):
                    smart_payload = {}

                # ── Persistance en base (non bloquant, cadencé) ────
                try:
                    insert_metric(hostname, agent_data, force=is_first)
                except Exception:
                    pass
                is_first = False

                computers_data[hostname] = agent_data

                # ── Log console (allégé : 1 ligne sur N) ───────────
                msg_count += 1
                if msg_count % AGENT_LOG_EVERY == 1:
                    smart_log = ""
                    if smart_payload.get("available"):
                        disks = smart_payload.get("disks", [])
                        smart_log = " | 💾 " + " ".join(
                            f"{d.get('disk','?')}:{d.get('health','?')} {d.get('temperature','?')}°C"
                            for d in disks
                            if d.get("available")
                        )

                    print(
                        f"📊 {hostname}: "
                        f"CPU={agent_data.get('cpu_percent', 0):.1f}% | "
                        f"RAM={agent_data.get('memory', {}).get('percent', 0):.1f}% | "
                        f"TCP={agent_data.get('protocols', {}).get('tcp', {}).get('established', 0)}"
                        f"{smart_log}"
                    )

                # ── Vérification des seuils + alertes ─────────────
                threshold_alerts = _check_thresholds(
                    hostname, agent_data, smart_payload
                )

                for msg, sev in threshold_alerts:
                    # Enrichissement : capture du contexte au moment de
                    # l'alerte (processus lourds, réseau) — Vili s'en sert
                    # pour l'analyse de cause racine.
                    details = None
                    try:
                        procs = sorted(
                            agent_data.get("processes") or [],
                            key=lambda p: p.get("cpu_percent", 0),
                            reverse=True,
                        )[:3]
                        net = agent_data.get("network") or {}
                        details = {
                            "top_processes": [
                                {
                                    "name": p.get("name"),
                                    "cpu_percent": p.get("cpu_percent"),
                                    "memory_percent": p.get("memory_percent"),
                                }
                                for p in procs
                            ],
                            "net_recv_kbps": round(net.get("bytes_recv_per_sec", 0) / 1024, 1),
                            "net_sent_kbps": round(net.get("bytes_sent_per_sec", 0) / 1024, 1),
                            "cpu": agent_data.get("cpu_percent"),
                            "ram": (agent_data.get("memory") or {}).get("percent"),
                        }
                    except Exception:
                        details = None

                    # Fenêtre de maintenance : on n'alerte pas
                    try:
                        from db.storage import is_in_maintenance

                        if is_in_maintenance(hostname):
                            continue
                    except Exception:
                        pass

                    try:
                        insert_notification(hostname, msg, sev, details=details)
                    except Exception:
                        pass
                    # dispatch vers les canaux sortants (webhook/email)
                    try:
                        import notify_out

                        notify_out.dispatch_alert(hostname, msg, sev)
                    except Exception:
                        pass
                    try:
                        await client_manager.broadcast(
                            {
                                "type": "alert",
                                "hostname": hostname,
                                "message": msg,
                                "severity": sev,
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                    except Exception as e:
                        print(f"⚠️  Échec broadcast alertes: {e}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"❌ Erreur agent {hostname}: {e}")
    finally:
        # ── Marquage hors ligne ────────────────────────────────────
        if hostname:
            data = computers_data.get(hostname, {})
            if data and not data.get("offline"):
                data["offline"] = True
                data["offline_since"] = datetime.now().isoformat()
                try:
                    insert_notification(hostname, "Agent hors ligne", "error")
                except Exception:
                    pass
                try:
                    await client_manager.broadcast(
                        {
                            "type": "alert",
                            "hostname": hostname,
                            "message": "Agent hors ligne",
                            "severity": "error",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                    await client_manager.broadcast(
                        {
                            "type": "agent_update",
                            "hostname": hostname,
                            "data": data,
                        }
                    )
                except Exception:
                    pass
            agent_manager.disconnect(hostname)


# ================================================================
#  SETUP
# ================================================================


def setup_websocket(app, computers_data):
    """Configure les endpoints WebSocket sur l'app FastAPI"""

    @app.on_event("startup")
    async def _capture_loop():
        set_main_loop(asyncio.get_running_loop())
        # Broadcaster global : un snapshot par seconde pour tous les clients
        asyncio.create_task(_broadcast_loop(computers_data))

    @app.websocket("/ws")
    async def websocket_web_clients(websocket: WebSocket):
        await web_client_endpoint(websocket, computers_data)

    @app.websocket("/ws/agent")
    async def websocket_agents(websocket: WebSocket):
        await agent_endpoint(websocket, computers_data)
