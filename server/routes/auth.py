import time

import auth as auth_mod
import config
from fastapi import Request
from fastapi.responses import RedirectResponse

# Anti force-brute simple en mémoire : {ip: [timestamps d'échec]}
_login_failures: dict = {}
_FAILURE_WINDOW = 300  # secondes


def _login_blocked(ip: str) -> bool:
    max_attempts = getattr(config, "LOGIN_MAX_ATTEMPTS", 10) or 10
    now = time.time()
    attempts = [t for t in _login_failures.get(ip, []) if now - t < _FAILURE_WINDOW]
    _login_failures[ip] = attempts
    return len(attempts) >= max_attempts


def _record_failure(ip: str):
    _login_failures.setdefault(ip, []).append(time.time())
    try:
        import security_events

        blocked = _login_blocked(ip)
        security_events.log_security_event(
            "login_failed",
            f"Échec de connexion depuis {ip}"
            + (" — IP temporairement bloquée" if blocked else ""),
            severity="critical" if blocked else "warning",
            source=ip,
        )
    except Exception:
        pass


def _clear_failures(ip: str):
    _login_failures.pop(ip, None)


def _session_cookie(resp, username: str):
    """Applique le cookie de session avec les attributs de sécurité."""
    ttl_hours = getattr(config, "SESSION_TTL_HOURS", 168) or 0
    resp.set_cookie(
        "session",
        auth_mod.make_token(username),
        httponly=True,
        samesite="lax",
        secure=bool(getattr(config, "COOKIE_SECURE", False)),
        max_age=int(ttl_hours * 3600) if ttl_hours > 0 else None,
    )
    return resp


def register(app, templates):
    """Rassemble les routes d'authentification et la page d'accueil."""

    def _requires_login(request: Request):
        if config.ENABLE_AUTH:
            cookie = request.cookies.get("session")
            user = auth_mod.verify_session(cookie) if cookie else None
            if not user:
                return RedirectResponse("/login")
            return user
        return None

    @app.get("/")
    def index(request: Request):
        check = _requires_login(request)
        if isinstance(check, RedirectResponse):
            return check
        return templates.TemplateResponse(
            request=request, name="index.html", context={"config": config}
        )

    @app.get("/login")
    def login_get(request: Request):
        """Formulaire de connexion (ou création si aucun utilisateur)."""
        if not config.ENABLE_AUTH:
            return RedirectResponse("/")
        users = auth_mod.load_users()
        first = len(users.get("users", {})) == 0
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"create": first, "error": None, "config": config},
        )

    @app.post("/login")
    async def login_post(request: Request):
        if not config.ENABLE_AUTH:
            return RedirectResponse("/")
        client_ip = request.client.host if request.client else "?"
        if _login_blocked(client_ip):
            try:
                import security_events

                security_events.log_blocked_once(
                    f"login:{client_ip}",
                    f"Tentatives de connexion depuis {client_ip} bloquées "
                    "(anti force-brute)",
                )
            except Exception:
                pass
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={
                    "create": False,
                    "error": "Trop de tentatives échouées — réessayez dans quelques minutes",
                    "config": config,
                },
                status_code=429,
            )
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
        users = auth_mod.load_users()
        first = len(users.get("users", {})) == 0
        if first:
            # create initial user
            auth_mod.create_user(username or "admin", password)
            resp = RedirectResponse("/", status_code=302)
            return _session_cookie(resp, username or "admin")
        else:
            if username and auth_mod.verify_credentials(username, password):
                _clear_failures(client_ip)
                resp = RedirectResponse("/", status_code=302)
                return _session_cookie(resp, username)
            else:
                _record_failure(client_ip)
                return templates.TemplateResponse(
                    request=request,
                    name="login.html",
                    context={
                        "create": False,
                        "error": "Identifiants invalides",
                        "config": config,
                    },
                    status_code=401,
                )

    @app.get("/logout")
    def logout(request: Request):
        resp = RedirectResponse("/" if not config.ENABLE_AUTH else "/login")
        resp.delete_cookie("session")
        return resp
