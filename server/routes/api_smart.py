"""
API routes pour les données S.M.A.R.T.
"""

from fastapi import Request
from fastapi.responses import JSONResponse


def register(app):
    @app.get("/api/computers/{hostname}/smart")
    def get_computer_smart_health(hostname: str, computers_data=None):
        """
        Retourne les données S.M.A.R.T. actuelles d'un ordinateur
        """
        # Import ici pour éviter les imports circulaires
        from server import computers_data as comp_data

        print(f"[DEBUG] API /api/computers/{hostname}/smart called")
        if hostname not in comp_data:
            print(f"[DEBUG] computer {hostname} not found in computers_data")
            return JSONResponse(
                {"error": f"Computer {hostname} not found"}, status_code=404
            )

        computer = comp_data.get(hostname, {})
        smart_data = computer.get("smart", {})
        print(f"[DEBUG] returning smart_data: {smart_data}")

        return {
            "hostname": hostname,
            "timestamp": computer.get("timestamp"),
            "smart": smart_data,
        }

    @app.get("/api/smart/summary")
    def get_smart_summary(computers_data=None):
        """
        Retourne un résumé de la santé S.M.A.R.T. de tous les ordinateurs
        """
        from server import computers_data as comp_data

        summary = {
            "total_computers": len(comp_data),
            "computers_with_smart": 0,
            "healthy": 0,
            "warnings": 0,
            "critical": 0,
            "details": [],
        }

        for hostname, data in comp_data.items():
            smart_data = data.get("smart", {})

            if not smart_data.get("available"):
                continue

            summary["computers_with_smart"] += 1

            # Déterminer le statut
            alerts = smart_data.get("alerts", [])
            disks_info = {
                "hostname": hostname,
                "disks": smart_data.get("disks", []),
                "alert_count": len(alerts),
                "status": (
                    "CRITICAL"
                    if any(a.get("level") == "CRITICAL" for a in alerts)
                    else "WARNING" if alerts else "OK"
                ),
            }

            summary["details"].append(disks_info)

            if disks_info["status"] == "CRITICAL":
                summary["critical"] += 1
            elif disks_info["status"] == "WARNING":
                summary["warnings"] += 1
            else:
                summary["healthy"] += 1

        return summary

    @app.get("/api/smart/alerts")
    def get_smart_alerts(computers_data=None):
        """
        Retourne toutes les alertes S.M.A.R.T. actives
        """
        from server import computers_data as comp_data

        all_alerts = []

        for hostname, data in comp_data.items():
            smart_data = data.get("smart", {})

            if not smart_data.get("available"):
                continue

            alerts = smart_data.get("alerts", [])
            timestamp = smart_data.get("timestamp")

            for alert in alerts:
                all_alerts.append(
                    {"hostname": hostname, "timestamp": timestamp, **alert}
                )

        # Trier par sévérité (CRITICAL d'abord)
        all_alerts.sort(
            key=lambda a: (
                0
                if a.get("level") == "CRITICAL"
                else 1 if a.get("level") == "WARNING" else 2
            )
        )

        return {
            "total_alerts": len(all_alerts),
            "critical_count": sum(
                1 for a in all_alerts if a.get("level") == "CRITICAL"
            ),
            "warning_count": sum(1 for a in all_alerts if a.get("level") == "WARNING"),
            "alerts": all_alerts,
        }

    @app.get("/api/smart/temperature")
    def get_disk_temperatures(computers_data=None):
        """
        Retourne la température de tous les disques
        """
        from server import computers_data as comp_data

        temperatures = {}

        for hostname, data in comp_data.items():
            smart_data = data.get("smart", {})

            if not smart_data.get("available"):
                continue

            disks = smart_data.get("disks", [])
            temperatures[hostname] = []

            for disk in disks:
                if disk.get("available"):
                    temp = disk.get("temperature")
                    if temp is not None:
                        temperatures[hostname].append(
                            {
                                "disk": disk.get("disk"),
                                "temperature": temp,
                                "power_on_hours": disk.get("power_on_hours"),
                                "health": disk.get("health"),
                            }
                        )

        return {
            "timestamp": data.get("timestamp") if data else None,
            "temperatures": temperatures,
        }
