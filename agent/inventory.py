"""
VIGIL — Collecte d'inventaire matériel & logiciel (côté agent).

Remonté lentement (au démarrage puis toutes les INVENTORY_INTERVAL
secondes, défaut 6 h) : le profil de la machine change rarement.
"""

import os
import platform
import socket
import sys
import time
from datetime import datetime

import psutil

AGENT_VERSION = "3.1"


def collect_inventory() -> dict:
    """Profil complet de la machine (lecture seule, sans droits requis)."""
    data = {
        "agent_version": AGENT_VERSION,
        "collected_at": datetime.now().isoformat(),
        "hostname": socket.gethostname(),
        "os": _os_info(),
        "kernel": platform.release(),
        "arch": platform.machine(),
        "python_version": sys.version.split()[0],
        "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
        "uptime_hours": round((time.time() - psutil.boot_time()) / 3600, 1),
        "cpu": _cpu_info(),
        "memory_total": psutil.virtual_memory().total,
        "swap_total": psutil.swap_memory().total,
        "disks": _disks(),
        "network": _network(),
    }
    return data


def _os_info() -> str:
    try:
        if sys.platform == "win32":
            return f"Windows {platform.release()} ({platform.version()})"
        name = ""
        try:
            import distro  # optionnel

            name = distro.name(pretty=True)
        except Exception:
            pass
        if not name:
            try:
                # /etc/os-release sans dépendance
                with open("/etc/os-release", encoding="utf-8") as f:
                    fields = dict(
                        line.strip().split("=", 1)
                        for line in f
                        if "=" in line
                    )
                name = fields.get("PRETTY_NAME", "")
            except Exception:
                name = platform.system()
        return (name or platform.system()).strip().strip('"')
    except Exception:
        return platform.platform()


def _cpu_info() -> dict:
    info = {
        "cores_logical": psutil.cpu_count(logical=True),
        "cores_physical": psutil.cpu_count(logical=False),
        "usage_percent": psutil.cpu_percent(interval=None),
    }
    try:
        if sys.platform == "win32":
            info["model"] = platform.processor() or "N/A"
        else:
            with open("/proc/cpuinfo", encoding="utf-8") as f:
                for line in f:
                    if line.lower().startswith("model name"):
                        info["model"] = line.split(":", 1)[1].strip()
                        break
            info.setdefault("model", platform.processor() or "N/A")
    except Exception:
        info["model"] = "N/A"
    return info


def _disks() -> list:
    disks = []
    try:
        for part in psutil.disk_partitions(all=False):
            if part.fstype.lower() in ("squashfs", "tmpfs", "devtmpfs", "iso9660"):
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except Exception:
                continue
            disks.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total": usage.total,
                "used": usage.used,
                "percent": usage.percent,
            })
    except Exception:
        pass
    return disks


def _network() -> list:
    out = []
    try:
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        for iface, if_addrs in addrs.items():
            entry = {"interface": iface, "up": stats[iface].isup if iface in stats else False}
            for a in if_addrs:
                if hasattr(psutil, "AF_LINK") and a.family == psutil.AF_LINK:
                    entry["mac"] = a.address
                elif a.family == socket.AF_INET:
                    entry["ipv4"] = a.address
                    entry["netmask"] = a.netmask
                elif a.family == socket.AF_INET6:
                    entry.setdefault("ipv6", a.address.split("%")[0])
            out.append(entry)
    except Exception:
        pass
    return out
