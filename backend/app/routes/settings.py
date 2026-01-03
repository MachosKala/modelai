from fastapi import APIRouter
from pydantic import BaseModel

from ..services.settings_store import (
    get_face_model,
    get_replicate_token,
    get_video_model,
    load_app_settings,
    save_app_settings,
)

router = APIRouter(prefix="/settings", tags=["Settings"])


class SettingsPayload(BaseModel):
    # Frontend dashboard fields
    apiBaseUrl: str | None = None
    replicateKey: str | None = None
    faceModel: str | None = None
    videoModel: str | None = None
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
        "faceModel": data.get("faceModel"),
        "videoModel": data.get("videoModel"),
        "lipsyncProvider": data.get("lipsyncProvider"),
        "elevenLabsKey": _mask(data.get("elevenLabsKey")),
        "syncLabsKey": _mask(data.get("syncLabsKey")),
        "didKey": _mask(data.get("didKey")),
        "effective": {
            "replicateTokenConfigured": bool(get_replicate_token()),
            "faceModel": get_face_model(),
            "videoModel": get_video_model(),
        },
    }


@router.post("")
async def save_settings(payload: SettingsPayload):
    """Save settings sent by the Settings dashboard (local use)."""
    current = load_app_settings()
    update = payload.model_dump(exclude_none=True)
    current.update(update)
    save_app_settings(current)
    return {"ok": True, "saved": sorted(update.keys())}


