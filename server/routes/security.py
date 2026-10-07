"""
VIGIL — Écran Sécurité : posture, événements et agents connectés.
"""

import config
from fastapi import FastAPI


def register(app: FastAPI):

    @app.get("/api/security/status")
    async def security_status():
        """Posture de sécurité + score + recommandations + événements."""
        auth_on = bool(config.ENABLE_AUTH)
        commands_on = bool(getattr(config, "AGENT_COMMANDS_ENABLED", False))
        cookie_secure = bool(getattr(config, "COOKIE_SECURE", False))
        agent_ips = list(getattr(config, "ALLOWED_AGENT_IPS", []) or [])
        client_ips = list(getattr(config, "ALLOWED_CLIENT_IPS", []) or [])
        session_ttl = int(getattr(config, "SESSION_TTL_HOURS", 168) or 0)

        checks = [
            {
                "id": "auth",
                "label": "Authentification activée",
                "ok": auth_on,
                "weight": 30,
                "advice": "Active ENABLE_AUTH (Paramètres → Sécurité) : sans elle, toute personne sur le réseau voit le dashboard et peut commander les agents.",
            },
            {
                "id": "command_guard",
                "label": "Commandes à distance sous contrôle",
                # danger seulement si commandes actives SANS auth
                "ok": not (commands_on and not auth_on),
                "weight": 25,
                "advice": "Les commandes à distance sont actives sans authentification : désactive AGENT_COMMANDS_ENABLED ou active ENABLE_AUTH immédiatement.",
            },
            {
                "id": "agent_whitelist",
                "label": "Liste blanche des agents",
                "ok": bool(agent_ips),
                "weight": 15,
                "advice": "Restreins ALLOWED_AGENT_IPS aux machines qui doivent vraiment se connecter.",
            },
            {
                "id": "client_whitelist",
                "label": "Liste blanche des navigateurs",
                "ok": bool(client_ips),
                "weight": 10,
                "advice": "Restreins ALLOWED_CLIENT_IPS aux postes d'administration.",
            },
            {
                "id": "session_ttl",
                "label": "Sessions à durée limitée",
                "ok": 0 < session_ttl <= 168,
                "weight": 10,
                "advice": "Fixe SESSION_TTL_HOURS entre 1 et 168h (7 jours max recommandé).",
            },
            {
                "id": "https",
                "label": "Cookies Secure (HTTPS)",
                "ok": cookie_secure,
                "weight": 10,
                "advice": "Une fois VIGIL derrière un reverse-proxy TLS, active COOKIE_SECURE.",
            },
        ]

        score = sum(c["weight"] for c in checks if c["ok"])
        recommendations = [c["advice"] for c in checks if not c["ok"]]

        import security_events

        from websocket_handler import agent_manager

        events = security_events.get_security_events(limit=50)
        failures_1h = security_events.count_recent_failures(3600)

        agents = [
            {
                "hostname": host,
                "local_ip": (app.state.computers_data.get(host) or {}).get("agent_ip"),
                "online": not (app.state.computers_data.get(host) or {}).get("offline"),
                "last_seen": (app.state.computers_data.get(host) or {}).get("last_seen"),
            }
            for host in agent_manager.get_all_agents()
        ]

        return {
            "score": score,
            "max_score": 100,
            "level": "good" if score >= 80 else ("warning" if score >= 50 else "critical"),
            "checks": checks,
            "recommendations": recommendations,
            "events": events,
            "failures_last_hour": failures_1h,
            "agents": agents,
            "config": {
                "ENABLE_AUTH": auth_on,
                "AGENT_COMMANDS_ENABLED": commands_on,
                "ALLOWED_AGENT_IPS": agent_ips,
                "ALLOWED_CLIENT_IPS": client_ips,
                "SESSION_TTL_HOURS": session_ttl,
                "COOKIE_SECURE": cookie_secure,
                "LOGIN_MAX_ATTEMPTS": int(getattr(config, "LOGIN_MAX_ATTEMPTS", 10) or 10),
            },
        }
