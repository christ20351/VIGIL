from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

# shared state (populated by setup_routes)
computers_data = {}
templates = None


def setup_routes(app: FastAPI, tmpl: Jinja2Templates, shared_data: dict):
    """Configure l'ensemble des routes en répartissant dans
    les sous-modules du package routes."""
    global computers_data, templates
    computers_data = shared_data
    templates = tmpl
    # also push into FastAPI state so submodules can use it if needed
    app.state.computers_data = shared_data
    app.state.templates = tmpl

    # import modules here so they see the updated globals if needed
    from . import (
        api_computers,
        api_history,
        api_notifications,
        api_settings,
        auth,
        health,
        legacy,
        update,
    )

    # register each group
    auth.register(app, templates)
    update.register(app)
    api_computers.register(app)
    api_settings.register(app)
    api_history.register(app)
    api_notifications.register(app)
    legacy.register(app)
    health.register(app)
    # index route lives in auth module as well (main page)
