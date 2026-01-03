from fastapi import APIRouter
from pydantic import BaseModel

from ..services.settings_store import load_app_settings, save_app_settings

router = APIRouter(prefix="/settings", tags=["Settings"])


class SettingsPayload(BaseModel):
    # Frontend dashboard fields
    replicateKey: str | None = None
    lipsyncProvider: str | None = None
    elevenLabsKey: str | None = None
    syncLabsKey: str | None = None
    didKey: str | None = None


@router.get("")
async def get_settings():
    """Return the saved (server-side) settings. Useful for debugging."""
    data = load_app_settings()
    # Never return full keys in plaintext (mask them)
    def _mask(value: str | None) -> str | None:
        if not value:
            return value
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}***{value[-4:]}"

    return {
        "replicateKey": _mask(data.get("replicateKey")),
        "lipsyncProvider": data.get("lipsyncProvider"),
        "elevenLabsKey": _mask(data.get("elevenLabsKey")),
        "syncLabsKey": _mask(data.get("syncLabsKey")),
        "didKey": _mask(data.get("didKey")),
    }


@router.post("")
async def save_settings(payload: SettingsPayload):
    """Save settings sent by the Settings dashboard (local use)."""
    current = load_app_settings()
    update = payload.model_dump(exclude_none=True)
    current.update(update)
    save_app_settings(current)
    return {"ok": True}


