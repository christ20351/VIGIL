"""
VIGIL - Module SMART Monitoring
Collecte les données de santé des disques via smartctl bundlé.
Compatible Windows & Linux, avec ou sans droits admin.
"""

import json
import os
import platform
import subprocess
import sys

# ================================================================
#  RÉSOLUTION DU BINAIRE SMARTCTL
# ================================================================


def _get_smartctl_path() -> str:
    """
    Cherche smartctl dans cet ordre :
    1. Binaire bundlé à côté du .exe (PyInstaller) ou du script (dev)
    2. smartctl installé sur le système (fallback)
    """
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))

    system = platform.system().lower()
    arch = platform.machine().lower()  # x86_64, aarch64, armv7l…

    # try both `bins/…` (used for release bundles) and `bin/…`
    if system == "windows":
        possible = [
            os.path.join(base, "bins", "windows", "smartctl.exe"),
            os.path.join(base, "bin", "windows", "smartctl.exe"),
            os.path.join(base, "bin", "smartctl.exe"),
        ]
    elif "aarch64" in arch or "arm64" in arch:
        possible = [
            os.path.join(base, "bins", "linux-arm64", "smartctl"),
            os.path.join(base, "bin", "linux", "smartctl"),
            os.path.join(base, "bin", "smartctl"),
        ]
    else:
        possible = [
            os.path.join(base, "bins", "linux-x86_64", "smartctl"),
            os.path.join(base, "bin", "linux", "smartctl"),
            os.path.join(base, "bin", "smartctl"),
        ]

    for bundled in possible:
        if os.path.exists(bundled):
            if system != "windows":
                try:
                    os.chmod(bundled, 0o755)
                except Exception:
                    pass
            return bundled

    # Fallback : smartctl dans le PATH système
    return "smartctl"


# ================================================================
#  DÉTECTION DES DISQUES
# ================================================================


def _detect_disks() -> list:
    """
    Retourne la liste des disques principaux selon l'OS.
    Ex : ['/dev/sda'] sur Linux, ['C:', 'D:'] sur Windows
    """
    system = platform.system().lower()

    if system == "windows":
        # Lister les lecteurs disponibles
        import ctypes
        import string

        drives = []
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drives.append(f"{letter}:")
            bitmask >>= 1
        return drives if drives else ["C:"]

    else:
        # Linux : chercher /dev/sdX et /dev/nvme0
        disks = []
        for name in sorted(os.listdir("/dev")):
            # Disques SATA/SAS (sda, sdb…) et NVMe (nvme0)
            if (name.startswith("sd") and len(name) == 3) or (
                name.startswith("nvme") and "n" not in name[4:]
            ):
                disks.append(f"/dev/{name}")
        return disks if disks else ["/dev/sda"]


# ================================================================
#  COLLECTE SMART D'UN DISQUE
# ================================================================


def _run_smartctl(smartctl: str, disk: str) -> dict | None:
    """
    Lance smartctl -a --json <disk> et retourne le JSON parsé.
    Retourne None en cas d'erreur.
    """
    try:
        result = subprocess.run(
            [smartctl, "-a", "--json=c", disk],
            capture_output=True,
            text=True,
            timeout=15,
        )
        # smartctl retourne exit code 0-7 selon les alertes,
        # le JSON est quand même présent même avec exit code != 0
        if result.stdout.strip():
            return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        print(f"[SMART] ⏱️  Timeout sur {disk}")
    except json.JSONDecodeError:
        print(f"[SMART] ⚠️  JSON invalide pour {disk}")
    except FileNotFoundError:
        print("[SMART] ❌ smartctl introuvable (ni bundlé, ni dans le PATH)")
    except Exception as e:
        print(f"[SMART] ❌ Erreur sur {disk}: {e}")
    return None


def _parse_smart(data: dict, disk: str) -> dict:
    """Extrait les métriques utiles depuis le JSON smartctl."""
    result = {
        "disk": disk,
        "available": True,
        "health": "UNKNOWN",
        "temperature": None,
        "power_on_hours": None,
        "reallocated_sectors": 0,
        "model": data.get("model_name", "Unknown"),
        "serial": data.get("serial_number", "Unknown"),
        "protocol": data.get("device", {}).get("protocol", "Unknown"),
    }

    # Santé globale
    smart_status = data.get("smart_status", {})
    if "passed" in smart_status:
        result["health"] = "PASSED" if smart_status["passed"] else "FAILED"

    # Température
    temp = data.get("temperature", {})
    result["temperature"] = temp.get("current")

    # Heures de fonctionnement
    power = data.get("power_on_time", {})
    result["power_on_hours"] = power.get("hours")

    # Secteurs défectueux réalloués (attribut ATA #5)
    attributes = data.get("ata_smart_attributes", {}).get("table", [])
    for attr in attributes:
        if attr.get("id") == 5:
            result["reallocated_sectors"] = attr.get("raw", {}).get("value", 0)
            break

    # NVMe : données spécifiques
    nvme_log = data.get("nvme_smart_health_information_log", {})
    if nvme_log:
        if result["temperature"] is None:
            result["temperature"] = nvme_log.get("temperature")
        result["reallocated_sectors"] = nvme_log.get("media_errors", 0)

    return result


# ================================================================
#  POINT D'ENTRÉE PRINCIPAL
# ================================================================


def get_all_disks_smart() -> list:
    """
    Retourne une liste de dicts avec les infos SMART de chaque disque.
    C'est cette fonction qui est appelée depuis agent.py.
    """
    smartctl = _get_smartctl_path()
    disks = _detect_disks()
    results = []

    for disk in disks:
        data = _run_smartctl(smartctl, disk)
        if data:
            results.append(_parse_smart(data, disk))
        else:
            results.append(
                {
                    "disk": disk,
                    "available": False,
                    "health": "UNKNOWN",
                    "temperature": None,
                    "power_on_hours": None,
                    "reallocated_sectors": 0,
                    "model": "Unknown",
                    "serial": "Unknown",
                    "protocol": "Unknown",
                }
            )

    return results


def check_smart_alerts(
    disks: list, temp_warning: int = 45, temp_critical: int = 55
) -> list:
    """
    Génère des alertes selon l'état SMART des disques.
    Retourne une liste d'alertes (peut être vide).
    """
    alerts = []

    for disk in disks:
        if not disk.get("available"):
            continue

        name = disk["disk"]

        # Alerte état FAILED
        if disk.get("health") == "FAILED":
            alerts.append(
                {
                    "level": "CRITICAL",
                    "disk": name,
                    "message": f"💀 Disque {name} en état FAILED — panne imminente !",
                }
            )

        # Alerte température critique
        temp = disk.get("temperature")
        if temp is not None:
            if temp >= temp_critical:
                alerts.append(
                    {
                        "level": "CRITICAL",
                        "disk": name,
                        "message": f"🔥 Température critique {name} : {temp}°C (seuil : {temp_critical}°C)",
                    }
                )
            elif temp >= temp_warning:
                alerts.append(
                    {
                        "level": "WARNING",
                        "disk": name,
                        "message": f"🌡️  Température élevée {name} : {temp}°C (seuil : {temp_warning}°C)",
                    }
                )

        # Alerte secteurs défectueux
        sectors = disk.get("reallocated_sectors", 0)
        if sectors and sectors > 0:
            alerts.append(
                {
                    "level": "WARNING",
                    "disk": name,
                    "message": f"⚠️  Secteurs réalloués sur {name} : {sectors}",
                }
            )

    return alerts
