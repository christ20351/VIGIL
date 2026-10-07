"""
Collecteurs de métriques système enrichis pour l'agent de monitoring VIGIL
"""

import socket
import sys
import time
from typing import Any, Dict, List
import psutil

PROCESS_LIMIT = 100

# Cache pour le calcul précis du % CPU de chaque processus entre deux collectes
_proc_cpu_tracker = {}
_pid_name_cache = {}


def get_network_protocols():
    """Récupère les connexions réseau par protocole avec résolution des processus et ports en écoute."""
    protocols = {
        "tcp": {
            "established": 0,
            "listen": 0,
            "time_wait": 0,
            "close_wait": 0,
            "syn_sent": 0,
            "fin_wait": 0,
            "connections": [],
        },
        "udp": {"total": 0, "connections": []},
        "listening_ports": [],
        "total": 0,
    }

    def _resolve_pid_name(pid):
        if not pid:
            return "Système"
        if pid in _pid_name_cache:
            return _pid_name_cache[pid]
        try:
            name = psutil.Process(pid).name()
            _pid_name_cache[pid] = name
            return name
        except Exception:
            return f"PID {pid}"

    try:
        connections = psutil.net_connections(kind="inet")

        listening_set = set()

        for conn in connections:
            protocols["total"] += 1
            proc_name = _resolve_pid_name(conn.pid)

            conn_info = {
                "local_addr": (
                    f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "N/A"
                ),
                "remote_addr": (
                    f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "N/A"
                ),
                "status": conn.status if hasattr(conn, "status") else "N/A",
                "pid": conn.pid,
                "process": proc_name,
            }

            if conn.type == socket.SOCK_STREAM:  # TCP
                status = (
                    conn.status.lower()
                    if hasattr(conn, "status") and isinstance(conn.status, str)
                    else str(conn.status if hasattr(conn, "status") else "").lower()
                )

                if "listen" in status:
                    protocols["tcp"]["listen"] += 1
                    if conn.laddr:
                        port_key = (conn.laddr.port, conn.laddr.ip, "TCP")
                        if port_key not in listening_set:
                            listening_set.add(port_key)
                            protocols["listening_ports"].append({
                                "port": conn.laddr.port,
                                "ip": conn.laddr.ip,
                                "protocol": "TCP",
                                "pid": conn.pid,
                                "process": proc_name,
                            })
                elif "established" in status:
                    protocols["tcp"]["established"] += 1
                    protocols["tcp"]["connections"].append(conn_info)
                elif "time_wait" in status:
                    protocols["tcp"]["time_wait"] += 1
                elif "close_wait" in status:
                    protocols["tcp"]["close_wait"] += 1
                elif "syn" in status:
                    protocols["tcp"]["syn_sent"] += 1
                elif "fin" in status:
                    protocols["tcp"]["fin_wait"] += 1

            elif conn.type == socket.SOCK_DGRAM:  # UDP
                protocols["udp"]["total"] += 1
                if conn.laddr:
                    port_key = (conn.laddr.port, conn.laddr.ip, "UDP")
                    if port_key not in listening_set:
                        listening_set.add(port_key)
                        protocols["listening_ports"].append({
                            "port": conn.laddr.port,
                            "ip": conn.laddr.ip,
                            "protocol": "UDP",
                            "pid": conn.pid,
                            "process": proc_name,
                        })
                protocols["udp"]["connections"].append(conn_info)

        # Trier les ports en écoute par numéro de port croissant
        protocols["listening_ports"].sort(key=lambda x: x["port"])
        protocols["listening_ports"] = protocols["listening_ports"][:30]

        # Conserver les 20 connexions actives les plus pertinentes
        protocols["tcp"]["connections"] = protocols["tcp"]["connections"][:20]
        protocols["udp"]["connections"] = protocols["udp"]["connections"][:15]

    except Exception as e:
        print(f"⚠️  Erreur protocoles: {e}")

    return protocols


def get_network_interfaces():
    """Récupère les informations complètes sur les interfaces réseau (IPs, MAC, MTU, stats, débit)."""
    interfaces = {}

    try:
        net_if_addrs = psutil.net_if_addrs()
        net_if_stats = psutil.net_if_stats()
        per_nic_io = psutil.net_io_counters(pernic=True)

        for interface, addrs in net_if_addrs.items():
            stat = net_if_stats.get(interface)
            nic_io = per_nic_io.get(interface)

            mac_addr = "N/A"
            parsed_addrs = []

            for addr in addrs:
                # AF_LINK sur BSD/macOS ou AF_PACKET sur Linux (MAC address)
                if hasattr(psutil, "AF_LINK") and addr.family == psutil.AF_LINK:
                    mac_addr = addr.address
                elif addr.family == getattr(socket, "AF_PACKET", -1):
                    mac_addr = addr.address
                elif addr.family == socket.AF_INET:  # IPv4
                    parsed_addrs.append({
                        "type": "IPv4",
                        "address": addr.address,
                        "netmask": addr.netmask or "N/A",
                        "broadcast": getattr(addr, "broadcast", None) or "N/A",
                    })
                elif addr.family == socket.AF_INET6:  # IPv6
                    parsed_addrs.append({
                        "type": "IPv6",
                        "address": addr.address.split("%")[0],  # Nettoie zone id
                    })

            interfaces[interface] = {
                "addresses": parsed_addrs,
                "mac": mac_addr,
                "is_up": stat.isup if stat else False,
                "speed": stat.speed if stat else 0,
                "mtu": stat.mtu if stat else 0,
                "duplex": str(stat.duplex).split(".")[-1] if stat and hasattr(stat, "duplex") else "N/A",
                "bytes_sent": nic_io.bytes_sent if nic_io else 0,
                "bytes_recv": nic_io.bytes_recv if nic_io else 0,
                "packets_sent": nic_io.packets_sent if nic_io else 0,
                "packets_recv": nic_io.packets_recv if nic_io else 0,
                "errin": nic_io.errin if nic_io else 0,
                "errout": nic_io.errout if nic_io else 0,
                "dropin": nic_io.dropin if nic_io else 0,
                "dropout": nic_io.dropout if nic_io else 0,
            }
    except Exception as e:
        print(f"⚠️  Erreur interfaces: {e}")

    return interfaces


def get_top_processes(limit=PROCESS_LIMIT):
    """
    Récupère la liste exhaustive des processus actifs (jusqu'à `limit`) avec calcul
    fidèle du CPU % par delta de temps et tri combiné CPU + RAM (Firefox, Antigravity, etc.).
    """
    global _proc_cpu_tracker
    now = time.time()
    num_cpus = psutil.cpu_count() or 1
    new_tracker = {}
    processes = []

    try:
        for proc in psutil.process_iter([
            "pid", "name", "memory_percent", "status", "username", "create_time"
        ]):
            try:
                pid = proc.info["pid"]
                name = proc.info.get("name") or "N/A"
                mem_pct = proc.info.get("memory_percent") or 0.0

                # Calcul du CPU % réel par delta de cpu_times
                try:
                    cpu_times = proc.cpu_times()
                    proc_time = cpu_times.user + cpu_times.system
                except Exception:
                    proc_time = 0.0

                cpu_pct = 0.0
                if pid in _proc_cpu_tracker:
                    last_time, last_proc_time = _proc_cpu_tracker[pid]
                    time_delta = now - last_time
                    if time_delta > 0.05:
                        cpu_delta = proc_time - last_proc_time
                        cpu_pct = max(0.0, min(100.0 * num_cpus, (cpu_delta / time_delta) * 100.0))

                new_tracker[pid] = (now, proc_time)

                pinfo = {
                    "pid": pid,
                    "name": name,
                    "cpu_percent": round(cpu_pct, 1),
                    "memory_percent": round(mem_pct, 1),
                    "status": str(proc.info.get("status") or "running"),
                    "username": str(proc.info.get("username") or "N/A"),
                }

                # Mémoire RSS détaillée
                try:
                    mem_info = proc.memory_info()
                    pinfo["memory_rss"] = mem_info.rss
                    pinfo["memory_vms"] = mem_info.vms
                except Exception:
                    pinfo["memory_rss"] = 0
                    pinfo["memory_vms"] = 0

                # I/O disque
                try:
                    io_info = proc.io_counters()
                    pinfo["io_read_bytes"] = io_info.read_bytes
                    pinfo["io_write_bytes"] = io_info.write_bytes
                except Exception:
                    pinfo["io_read_bytes"] = 0
                    pinfo["io_write_bytes"] = 0

                processes.append(pinfo)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        _proc_cpu_tracker = new_tracker

        # Tri intelligent : priorise les processus actifs en CPU ET ceux qui consomment de la RAM
        # (ex: navigateurs, IDEs comme Antigravity / Firefox / Code)
        processes.sort(
            key=lambda x: (
                x["cpu_percent"] * 3.0
                + x["memory_percent"] * 1.5
                + (x["memory_rss"] / 50_000_000.0)
            ),
            reverse=True,
        )

    except Exception as e:
        print(f"⚠️  Erreur collecte processus: {e}")

    return processes[:limit]
