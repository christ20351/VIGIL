"""
Collecteurs d'informations système pour l'agent de monitoring
"""

import sys
import time

import psutil
from collectors import get_network_interfaces, get_network_protocols, get_top_processes

# Variables globales pour calculer le débit réseau
last_net_io = None
last_time = None


def get_system_info():
    """Collecte toutes les informations système"""
    global last_net_io, last_time

    current_net_io = psutil.net_io_counters()
    current_time = time.time()

    # Calcul du débit réseau
    if last_net_io is not None and last_time is not None:
        time_delta = current_time - last_time
        if time_delta > 0:
            bytes_sent_per_sec = (
                current_net_io.bytes_sent - last_net_io.bytes_sent
            ) / time_delta
            bytes_recv_per_sec = (
                current_net_io.bytes_recv - last_net_io.bytes_recv
            ) / time_delta
        else:
            bytes_sent_per_sec = 0
            bytes_recv_per_sec = 0
    else:
        bytes_sent_per_sec = 0
        bytes_recv_per_sec = 0

    last_net_io = current_net_io
    last_time = current_time

    # Récupération du nombre de connexions actives
    try:
        connections = psutil.net_connections(kind="inet")
        active_connections = len(
            [
                c
                for c in connections
                if hasattr(c, "status") and "established" in str(c.status).lower()
            ]
        )
    except:
        active_connections = 0

    # Informations disque (compatible multi-OS)
    try:
        if sys.platform == "win32":
            disk_path = "C:\\"
        else:
            disk_path = "/"
        disk_info = psutil.disk_usage(disk_path)
    except:
        disk_info = psutil.disk_usage("/")

    import socket

    hostname = socket.gethostname()
    from datetime import datetime

    return {
        "hostname": hostname,
        "timestamp": datetime.now().isoformat(),
        "system": sys.platform,
        "system_version": (
            psutil.os_version() if hasattr(psutil, "os_version") else "N/A"
        ),
        "architecture": (
            psutil.architecture()[0] if hasattr(psutil, "architecture") else "N/A"
        ),
        "cpu_percent": psutil.cpu_percent(interval=None),
        "cpu_count": psutil.cpu_count(),
        "memory": {
            "total": psutil.virtual_memory().total,
            "available": psutil.virtual_memory().available,
            "percent": psutil.virtual_memory().percent,
            "used": psutil.virtual_memory().used,
        },
        "disk": {
            "total": disk_info.total,
            "used": disk_info.used,
            "free": disk_info.free,
            "percent": disk_info.percent,
        },
        "network": {
            "bytes_sent": current_net_io.bytes_sent,
            "bytes_recv": current_net_io.bytes_recv,
            "bytes_sent_per_sec": bytes_sent_per_sec,
            "bytes_recv_per_sec": bytes_recv_per_sec,
            "packets_sent": current_net_io.packets_sent,
            "packets_recv": current_net_io.packets_recv,
            "active_connections": active_connections,
        },
        "protocols": get_network_protocols(),
        "processes": get_top_processes(limit=10),
        "interfaces": get_network_interfaces(),
    }
