"""Token storage and configuration management."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "plaud-cli"
    return Path.home() / ".config" / "plaud-cli"


def _config_file() -> Path:
    return _config_dir() / "config.yaml"


def _load_config() -> dict[str, Any]:
    import yaml
    cfg = _config_file()
    if cfg.exists():
        try:
            data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def _save_config(data: dict[str, Any]) -> None:
    import yaml
    cfg = _config_file()
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8")


def get_token() -> str | None:
    """Return the token stored in config.yaml."""
    return _load_config().get("token") or None


def save_token(token: str) -> str:
    """Persist the token to config.yaml. Returns 'file'."""
    cfg = _load_config()
    cfg["token"] = token
    _save_config(cfg)
    return "file"


def delete_token() -> None:
    """Remove the token from config.yaml."""
    cfg = _load_config()
    cfg.pop("token", None)
    _save_config(cfg)


def get_api_base() -> str:
    cfg = _load_config()
    return cfg.get("api_base", "https://api.plaud.ai")


def set_api_base(url: str) -> None:
    cfg = _load_config()
    cfg["api_base"] = url.rstrip("/")
    _save_config(cfg)
