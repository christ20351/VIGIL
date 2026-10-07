"""
Vili — Boucle de surveillance autonome en arrière-plan (suivi continu).

Trois étages :
1. Cycle rapide (30 s) : détection règle-based + **évaluation des règles
   de surveillance en langage naturel** — toujours actif, même sans LLM.
2. Scan réactif : dès que la couche d'intelligence détecte une anomalie,
   une tempête d'incidents ou une saturation imminente, Vili (LLM) est
   convoqué immédiatement (cooldown) sans attendre le cycle complet.
3. Cycle IA complet (AI_SCAN_INTERVAL, 300 s) + **rapport quotidien**
   planifié (DAILY_REPORT_HOUR) : analyse complète, décisions, actions.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict

from ai.agent_diag import diagnose_single_agent
from ai.autonomous_db import save_autonomous_ai_report
from db.storage import insert_notification

logger = logging.getLogger("vigil.ai.autonomous")

# cooldowns internes
_REACTIVE_COOLDOWN = 900  # scan réactif max toutes les 15 min
_DAILY_CHECK_INTERVAL = 300  # vérification de l'heure du rapport (5 min)


class AutonomousAgentWatchdog:
    def __init__(self, computers_data: Dict[str, Any], check_interval: int = 30):
        self.computers_data = computers_data
        self.check_interval = check_interval
        self._cooldowns = {}
        self._running = False
        self._thread = None
        self._last_ai_cycle = 0.0
        self._ai_cycle_busy = False
        self._last_reactive = 0.0
        self._last_daily_report_date = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="AIWatchdog")
        self._thread.start()
        threading.Thread(
            target=self._daily_report_loop, daemon=True, name="ViliDailyReport"
        ).start()
        logger.info(
            f"Vili autonomous watchdog started (fast cycle: {self.check_interval}s, "
            f"reactive + daily report enabled)"
        )

    def _run_loop(self):
        while self._running:
            try:
                self.run_scan_cycle()
            except Exception as e:
                logger.error(f"Error in Vili fast cycle: {e}")

            # ── Suivi continu : règles de surveillance admin ─────────
            try:
                from ai.watch import evaluate_watch_rules

                evaluate_watch_rules(self.computers_data)
            except Exception as e:
                logger.debug(f"watch rules eval error: {e}")

            # ── Scan réactif sur anomalie/incident détecté ───────────
            try:
                self._maybe_react_to_events()
            except Exception as e:
                logger.debug(f"reactive scan error: {e}")

            # ── Cycle IA complet de Vili (décisions + actions) ───────
            try:
                self._maybe_run_ai_cycle()
            except Exception as e:
                logger.error(f"Error in Vili AI cycle: {e}")

            time.sleep(self.check_interval)

    def run_scan_cycle(self) -> int:
        """Cycle rapide règle-based : détection d'incidents."""
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
                    title = f"🤖 Incident détecté : {host} ({status})"
                    severity = "critical" if status == "CRITICAL" else "warning"
                    summary = diag["summary"]

                    save_autonomous_ai_report(host, title, severity, summary, diag)
                    reports_created += 1

                    insert_notification(host, f"🤖 [Vili] {title} - {summary}", severity=severity)

        return reports_created

    # ----------------------------------------------------------------
    #  Scan réactif : Vili convoqué immédiatement quand ça se passe mal
    # ----------------------------------------------------------------
    def _maybe_react_to_events(self):
        import config as _config

        if not getattr(_config, "AI_ENABLED", True):
            return
        if not self._llm_configured():
            return
        if time.time() - self._last_reactive < _REACTIVE_COOLDOWN:
            return

        from ai.analytics import get_intelligence_report

        rep = get_intelligence_report(self.computers_data)
        urgent = (
            rep["summary"]["anomalies_count"] > 0
            or rep["summary"]["storm_detected"]
            or (rep["summary"]["forecasts_count"] > 0
                and rep["forecasts"][0]["days_left"] < 1.0)
        )
        if not urgent:
            return

        self._last_reactive = time.time()
        logger.info(
            f"Vili réactif déclenché (anomalies={rep['summary']['anomalies_count']}, "
            f"tempête={rep['summary']['storm_detected']}, "
            f"saturation<24h={rep['summary']['forecasts_count'] and rep['forecasts'][0]['days_left'] < 1.0})"
        )
        try:
            from ai.actions import run_vili_decision_cycle

            run_vili_decision_cycle(self.computers_data)
        except Exception as e:
            logger.warning(f"Vili reactive cycle failed: {e}")

    def _llm_configured(self) -> bool:
        import config as _config

        provider = (getattr(_config, "AI_PROVIDER", "auto_rule") or "auto_rule").lower()
        if provider == "auto_rule":
            return bool(getattr(_config, "AI_API_KEY", ""))
        if provider == "ollama":
            return True  # local, on tente
        return bool(getattr(_config, "AI_API_KEY", ""))

    # ----------------------------------------------------------------
    #  Cycle IA complet
    # ----------------------------------------------------------------
    def _maybe_run_ai_cycle(self):
        import config as _config

        if not getattr(_config, "AI_ENABLED", True):
            return
        if not self._llm_configured():
            return

        interval = max(60, int(getattr(_config, "AI_SCAN_INTERVAL", 300) or 300))
        now = time.time()
        if self._ai_cycle_busy or now - self._last_ai_cycle < interval:
            return

        self._ai_cycle_busy = True
        self._last_ai_cycle = now
        try:
            from ai.actions import run_vili_decision_cycle

            result = run_vili_decision_cycle(self.computers_data)
            logger.info(
                f"Vili AI cycle done (mode {result.get('mode')}, "
                f"{len(result.get('actions_taken', []))} action(s))"
            )
        except Exception as e:
            logger.warning(f"Vili AI cycle failed: {e}")
        finally:
            self._ai_cycle_busy = False

    # ----------------------------------------------------------------
    #  Rapport quotidien planifié
    # ----------------------------------------------------------------
    def _daily_report_loop(self):
        while self._running:
            time.sleep(_DAILY_CHECK_INTERVAL)
            try:
                import config as _config

                if not getattr(_config, "DAILY_REPORT_ENABLED", True):
                    continue
                if not self._llm_configured():
                    continue

                hour = int(getattr(_config, "DAILY_REPORT_HOUR", 8) or 8)
                now = datetime.now()
                today = now.strftime("%Y-%m-%d")
                if now.hour != hour or self._last_daily_report_date == today:
                    continue

                self._last_daily_report_date = today
                logger.info("Génération du rapport quotidien Vili...")
                from ai.actions import generate_daily_report

                generate_daily_report(self.computers_data)
            except Exception as e:
                logger.warning(f"Daily report failed: {e}")
