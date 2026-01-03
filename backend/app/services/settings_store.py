import json
import logging
from pathlib import Path
from typing import Any

from ..config import settings

logger = logging.getLogger(__name__)

_SETTINGS_FILE = Path(settings.storage_path) / "app_settings.json"


def load_app_settings() -> dict[str, Any]:
    if not _SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Failed to read {_SETTINGS_FILE}: {e}")
        return {}


def save_app_settings(data: dict[str, Any]) -> None:
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_replicate_token() -> str:
    # Prefer .env, fallback to saved settings from dashboard
    if settings.replicate_api_token:
        return settings.replicate_api_token
    stored = load_app_settings()
    token = (stored.get("replicateKey") or "").strip()
    return token


