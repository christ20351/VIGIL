"""
Collecteurs de métriques système pour l'agent de monitoring
"""

import socket
import sys
import time
from collections import defaultdict

import psutil


def get_network_protocols():
    """Récupère les connexions réseau par protocole"""
    protocols = {
        "tcp": {
            "established": 0,
            "listen": 0,
            "time_wait": 0,
            "close_wait": 0,
            "connections": [],
        },
        "udp": {"total": 0, "connections": []},
        "total": 0,
    }

    try:
        connections = psutil.net_connections(kind="inet")

        for conn in connections:
            protocols["total"] += 1

            # Informations de la connexion
            conn_info = {
                "local_addr": (
                    f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "N/A"
                ),
                "remote_addr": (
                    f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "N/A"
                ),
                "status": conn.status if hasattr(conn, "status") else "N/A",
                "pid": conn.pid,
            }

            if conn.type == socket.SOCK_STREAM:  # TCP
                protocols["tcp"]["connections"].append(conn_info)

                if hasattr(conn, "status"):
                    status = (
                        conn.status.lower()
                        if isinstance(conn.status, str)
                        else str(conn.status)
                    )
                    if "established" in status:
                        protocols["tcp"]["established"] += 1
                    elif "listen" in status:
                        protocols["tcp"]["listen"] += 1
                    elif "time_wait" in status:
                        protocols["tcp"]["time_wait"] += 1
                    elif "close_wait" in status:
                        protocols["tcp"]["close_wait"] += 1

            elif conn.type == socket.SOCK_DGRAM:  # UDP
                protocols["udp"]["total"] += 1
                protocols["udp"]["connections"].append(conn_info)

        # Limiter le nombre de connexions conservées
        protocols["tcp"]["connections"] = protocols["tcp"]["connections"][:10]
        protocols["udp"]["connections"] = protocols["udp"]["connections"][:10]

    except Exception as e:
        print(f"⚠️  Erreur protocoles: {e}")

    return protocols


def get_network_interfaces():
    """Récupère les informations sur les interfaces réseau"""
    interfaces = {}

    try:
        net_if_addrs = psutil.net_if_addrs()
        net_if_stats = psutil.net_if_stats()

        for interface, addrs in net_if_addrs.items():
            interfaces[interface] = {
                "addresses": [],
                "is_up": (
                    net_if_stats[interface].isup if interface in net_if_stats else False
                ),
                "speed": (
                    net_if_stats[interface].speed if interface in net_if_stats else 0
                ),
            }

            for addr in addrs:
                if addr.family == socket.AF_INET:  # IPv4
                    interfaces[interface]["addresses"].append(
                        {
                            "type": "IPv4",
                            "address": addr.address,
                            "netmask": addr.netmask,
                        }
                    )
                elif addr.family == socket.AF_INET6:  # IPv6
                    interfaces[interface]["addresses"].append(
                        {"type": "IPv6", "address": addr.address}
                    )
    except Exception as e:
        print(f"⚠️  Erreur interfaces: {e}")

    return interfaces


def get_top_processes(limit=10):
    """Récupère les processus les plus gourmands en CPU avec détails"""
    processes = []

    try:
        for proc in psutil.process_iter(
            ["pid", "name", "cpu_percent", "memory_percent", "status", "username"]
        ):
            try:
                pinfo = proc.info
                pinfo["cpu_percent"] = proc.cpu_percent(interval=None)
                pinfo["memory_percent"] = proc.memory_percent()

                # Ajouter les infos de mémoire détaillées
                try:
                    mem_info = proc.memory_info()
                    pinfo["memory_rss"] = mem_info.rss  # RAM utilisée en bytes
                    pinfo["memory_vms"] = mem_info.vms  # Mémoire virtuelle en bytes
                except:
                    pinfo["memory_rss"] = 0
                    pinfo["memory_vms"] = 0

                # Ajouter l'IO disque si disponible
                try:
                    io_info = proc.io_counters()
                    pinfo["io_read_bytes"] = io_info.read_bytes  # Bytes lus
                    pinfo["io_write_bytes"] = io_info.write_bytes  # Bytes écrits
                except:
                    pinfo["io_read_bytes"] = 0
                    pinfo["io_write_bytes"] = 0

                # Bloquer les valeurs None
                for key in pinfo:
                    if pinfo[key] is None:
                        pinfo[key] = "N/A"

                processes.append(pinfo)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        # Trier par utilisation CPU décroissante
        processes = sorted(
            processes,
            key=lambda x: (
                x["cpu_percent"] if isinstance(x["cpu_percent"], (int, float)) else 0
            ),
            reverse=True,
        )[:limit]

    except Exception as e:
        print(f"⚠️  Erreur processus: {e}")

    return processes
