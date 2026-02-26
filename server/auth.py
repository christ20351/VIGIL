import binascii
import hashlib
import hmac
import os
from typing import Optional

import config
import yaml

USERS_PATH = os.path.join(os.path.dirname(__file__), "users.yaml")


def _load_users() -> dict:
    try:
        with open(USERS_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        data = {}
    # ensure structure
    if "users" not in data:
        data["users"] = {}
    return data


def _save_users(data: dict) -> None:
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f)


def load_users() -> dict:
    """Retourne le contenu du fichier `users.yaml` sous forme de dict."""
    return _load_users()


def create_user(username: str, password: str) -> None:
    """Ajoute un nouvel utilisateur avec mot de passe hashé."""
    data = _load_users()
    hashed = _hash_password(password)
    data["users"][username] = hashed
    _save_users(data)


def verify_credentials(username: str, password: str) -> bool:
    data = _load_users()
    stored = data.get("users", {}).get(username)
    if not stored:
        return False
    return _verify_password(stored, password)


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    pwdhash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return binascii.hexlify(salt + pwdhash).decode()


def _verify_password(stored_hash: str, password: str) -> bool:
    try:
        data = binascii.unhexlify(stored_hash.encode())
        salt = data[:16]
        stored = data[16:]
        pwdhash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
        return hmac.compare_digest(pwdhash, stored)
    except Exception:
        return False


def make_token(username: str) -> str:
    """Génère un jeton de session signé"""
    secret = config.AUTH_TOKEN or ""
    msg = username.encode()
    sig = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    return f"{username}:{sig}"


def verify_session(token: Optional[str]) -> Optional[str]:
    """Vérifie un cookie de session et retourne l'utilisateur s'il est valide."""
    if not token:
        return None
    try:
        username, sig = token.split(":", 1)
        expected = hmac.new(
            config.AUTH_TOKEN.encode(), username.encode(), hashlib.sha256
        ).hexdigest()
        if hmac.compare_digest(sig, expected):
            return username
    except Exception:
        pass
    return None
