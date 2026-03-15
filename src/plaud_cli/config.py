"""Token storage and configuration management."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Set by the --config CLI switch on the root group before any subcommand runs.
_override_config_path: Path | None = None


def set_config_path(path: str | Path) -> None:
    """Override the config file location for the lifetime of this process."""
    global _override_config_path
    _override_config_path = Path(path)


def _config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "plaud-cli"
    return Path.home() / ".config" / "plaud-cli"


def _config_file() -> Path:
    if _override_config_path is not None:
        return _override_config_path
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
    """Persist the token to config.yaml. Returns the config file path."""
    data = _load_config()
    data["token"] = token
    _save_config(data)
    return str(_config_file())


def delete_token() -> None:
    """Remove the token from config.yaml."""
    data = _load_config()
    data.pop("token", None)
    _save_config(data)


def get_api_base() -> str:
    return _load_config().get("api_base", "https://api.plaud.ai")


def set_api_base(url: str) -> None:
    data = _load_config()
    data["api_base"] = url.rstrip("/")
    _save_config(data)
