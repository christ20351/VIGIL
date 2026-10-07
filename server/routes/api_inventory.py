"""
VIGIL — Inventaire matériel & logiciel : API + export CSV.
"""

import csv
import io

from fastapi import FastAPI
from fastapi.responses import StreamingResponse


def register(app: FastAPI):

    @app.get("/api/inventory")
    def inventory_list():
        from db.storage import get_agent_meta, list_inventory

        out = []
        for item in list_inventory():
            meta = get_agent_meta(item["hostname"])
            out.append({
                **item,
                "group": meta.get("group_name") or "",
            })
        return out

    @app.get("/api/inventory/{hostname}")
    def inventory_detail(hostname: str):
        from db.storage import get_inventory

        item = get_inventory(hostname)
        if not item:
            from fastapi.responses import JSONResponse

            return JSONResponse({"error": "Inventaire indisponible"}, status_code=404)
        return item

    @app.get("/api/inventory/export/csv")
    def inventory_export_csv():
        from db.storage import get_agent_meta, list_inventory

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "hostname", "groupe", "os", "kernel", "arch", "cpu_model",
            "cores", "ram_go", "disque_principal", "disque_pct",
            "ip", "uptime_h", "agent_version", "inventaire_le",
        ])
        for item in list_inventory():
            d = item.get("data") or {}
            cpu = d.get("cpu") or {}
            disks = d.get("disks") or []
            main_disk = disks[0] if disks else {}
            ipv4 = ""
            for nic in d.get("network") or []:
                if nic.get("ipv4") and nic.get("ipv4") != "127.0.0.1":
                    ipv4 = nic["ipv4"]
                    break
            meta = get_agent_meta(item["hostname"])
            writer.writerow([
                item["hostname"],
                meta.get("group_name") or "",
                d.get("os", ""),
                d.get("kernel", ""),
                d.get("arch", ""),
                cpu.get("model", ""),
                cpu.get("cores_logical", ""),
                round((d.get("memory_total") or 0) / 1e9, 1),
                main_disk.get("device", ""),
                main_disk.get("percent", ""),
                ipv4,
                d.get("uptime_hours", ""),
                d.get("agent_version", ""),
                item.get("ts", ""),
            ])
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=vigil_inventaire.csv"
            },
        )
