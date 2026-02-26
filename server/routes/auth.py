import auth as auth_mod
import config
from fastapi import Request
from fastapi.responses import RedirectResponse


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
            "index.html", {"request": request, "config": config}
        )

    @app.get("/login")
    def login_get(request: Request):
        """Formulaire de connexion (ou création si aucun utilisateur)."""
        users = auth_mod.load_users()
        first = len(users.get("users", {})) == 0
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "create": first, "error": None, "config": config},
        )

    @app.post("/login")
    async def login_post(request: Request):
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
        users = auth_mod.load_users()
        first = len(users.get("users", {})) == 0
        if first:
            # create initial user
            auth_mod.create_user(username or "admin", password)
            resp = RedirectResponse("/", status_code=302)
            token = auth_mod.make_token(username or "admin")
            resp.set_cookie("session", token, httponly=True)
            return resp
        else:
            if auth_mod.verify_credentials(username, password):
                resp = RedirectResponse("/", status_code=302)
                resp.set_cookie("session", auth_mod.make_token(username), httponly=True)
                return resp
            else:
                return templates.TemplateResponse(
                    "login.html",
                    {
                        "request": request,
                        "create": False,
                        "error": "Identifiants invalides",
                        "config": config,
                    },
                )

    @app.get("/logout")
    def logout(request: Request):
        resp = RedirectResponse("/login")
        resp.delete_cookie("session")
        return resp
