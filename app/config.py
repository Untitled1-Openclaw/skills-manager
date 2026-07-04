from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

import bcrypt


DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"


@dataclass(frozen=True)
class Settings:
    skills_root: Path
    config_path: Path
    host: str
    port: int
    secure_cookies: bool


def get_settings() -> Settings:
    skills_root = Path(os.getenv("SKILLS_MANAGER_ROOT", "/home/user/.local/share/skills")).expanduser()
    config_path = Path(
        os.getenv("SKILLS_MANAGER_CONFIG", "/home/user/.config/skills-manager/config.json")
    ).expanduser()
    return Settings(
        skills_root=skills_root,
        config_path=config_path,
        host=os.getenv("SKILLS_MANAGER_HOST", "127.0.0.1"),
        port=int(os.getenv("SKILLS_MANAGER_PORT", "8098")),
        secure_cookies=os.getenv("SKILLS_MANAGER_SECURE_COOKIES", "").lower() in {"1", "true", "yes", "on"},
    )


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def ensure_config(settings: Settings) -> dict:
    settings.skills_root.mkdir(parents=True, exist_ok=True)
    settings.config_path.parent.mkdir(parents=True, exist_ok=True)
    if settings.config_path.exists():
        with settings.config_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    config = {
        "username": os.getenv("SKILLS_MANAGER_DEFAULT_USER", DEFAULT_USERNAME),
        "password_hash": _hash_password(os.getenv("SKILLS_MANAGER_DEFAULT_PASSWORD", DEFAULT_PASSWORD)),
        "session_secret": secrets.token_urlsafe(32),
    }
    save_config(settings, config)
    return config


def save_config(settings: Settings, config: dict) -> None:
    settings.config_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = settings.config_path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
    tmp_path.replace(settings.config_path)


def change_password(settings: Settings, config: dict, new_password: str) -> dict:
    updated = dict(config)
    updated["password_hash"] = _hash_password(new_password)
    save_config(settings, updated)
    return updated
