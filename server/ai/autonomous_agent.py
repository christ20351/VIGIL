"""
VIGIL AI — Background Autonomous Watchdog Agent Loop (< 100 lines)
"""

import logging
import threading
import time
from typing import Any, Dict
from ai.agent_diag import diagnose_single_agent
from ai.autonomous_db import save_autonomous_ai_report
from db.storage import insert_notification

logger = logging.getLogger("vigil.ai.autonomous")


class AutonomousAgentWatchdog:
    def __init__(self, computers_data: Dict[str, Any], check_interval: int = 30):
        self.computers_data = computers_data
        self.check_interval = check_interval
        self._cooldowns = {}
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="AIWatchdog")
        self._thread.start()
        logger.info(f"Autonomous AI Watchdog started (interval: {self.check_interval}s)")

    def _run_loop(self):
        while self._running:
            try:
                self.run_scan_cycle()
            except Exception as e:
                logger.error(f"Error in AI Watchdog cycle: {e}")
            time.sleep(self.check_interval)

    def run_scan_cycle(self) -> int:
        """Exécute un cycle de détection autonome d'incidents."""
        reports_created = 0
        now = time.time()

        for host, data in list(self.computers_data.items()):
            diag = diagnose_single_agent(host, data)
            status = diag["status"]

            if status in ["CRITICAL", "WARNING"]:
                cooldown_key = f"{host}_{status}"
                last_time = self._cooldowns.get(cooldown_key, 0)

                # Éviter le spam (cooldown de 10 min par incident)
                if now - last_time > 600:
                    self._cooldowns[cooldown_key] = now
                    title = f"🤖 Incident Autonome IA : {host} ({status})"
                    severity = "critical" if status == "CRITICAL" else "warning"
                    summary = diag["summary"]

                    # Sauvegarde SQLite
                    report_id = save_autonomous_ai_report(host, title, severity, summary, diag)
                    reports_created += 1

                    # Insertion notification
                    insert_notification(host, f"🤖 [IA Autonome] {title} - {summary}", severity=severity)

        return reports_created
