import asyncio
import logging
import time
from typing import Any, Callable, Optional

import httpx

logger = logging.getLogger(__name__)


class ReplicateHTTPError(RuntimeError):
    pass


class ReplicateClient:
    """
    Minimal Replicate REST client (no replicate python SDK), compatible with Python 3.14+.
    Docs: https://replicate.com/docs/reference/http
    """

    def __init__(self, api_token: str, base_url: str = "https://api.replicate.com/v1"):
        self.api_token = api_token.strip() if api_token else ""
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        if not self.api_token:
            raise ReplicateHTTPError(
                "Missing Replicate API token. Set REPLICATE_API_TOKEN in backend/.env "
                "or save it from the Settings dashboard."
            )
        return {
            "Authorization": f"Token {self.api_token}",
            "Content-Type": "application/json",
        }

    def _auth_headers(self) -> dict[str, str]:
        # For multipart requests we MUST NOT set Content-Type manually.
        if not self.api_token:
            raise ReplicateHTTPError(
                "Missing Replicate API token. Set REPLICATE_API_TOKEN in backend/.env "
                "or save it from the Settings dashboard."
            )
        return {"Authorization": f"Token {self.api_token}"}

    async def upload_file(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str | None = None,
    ) -> str:
        """
        Upload a file to Replicate and return a URL that can be used as a model input.

        Endpoint: POST /v1/files (multipart/form-data)
        """
        # Replicate Files API expects multipart field name "content" (not "file").
        # See: https://api.replicate.com/openapi.json -> POST /files
        files = {
            "content": (filename or "upload.bin", content, content_type or "application/octet-stream"),
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/files",
                headers=self._auth_headers(),
                files=files,
            )
        if resp.status_code >= 400:
            raise ReplicateHTTPError(f"Replicate file upload failed: {resp.status_code} {resp.text}")

        data = resp.json()
        urls = data.get("urls") or {}
        file_url = urls.get("get") or urls.get("download") or data.get("url")
        if not file_url:
            raise ReplicateHTTPError("Replicate file upload succeeded but no file URL was returned.")
        return str(file_url)

    async def create_prediction(self, *, model: str, input: dict[str, Any]) -> dict[str, Any]:
        """
        Create a prediction.

        Supports:
        - model slug: "owner/name"
        - model slug pinned to version: "owner/name:version_id_or_hash"

        Replicate's HTTP API supports multiple ways to create predictions depending on the endpoint.
        We try the most convenient method first and fall back when needed.
        """

        owner, name, version = _parse_model_identifier(model)

        async with httpx.AsyncClient(timeout=60.0) as client:
            # If model includes an explicit version, use /predictions with version.
            if version:
                resp = await client.post(
                    f"{self.base_url}/predictions",
                    headers=self._headers(),
                    json={"version": version, "input": input},
                )
                if resp.status_code >= 400:
                    raise ReplicateHTTPError(f"Replicate create_prediction failed: {resp.status_code} {resp.text}")
                return resp.json()

            # Prefer "run by model" endpoint (no need to resolve version)
            resp = await client.post(
                f"{self.base_url}/models/{owner}/{name}/predictions",
                headers=self._headers(),
                json={"input": input},
            )
            if resp.status_code < 400:
                return resp.json()

            # Fallback: resolve latest version then call /predictions
            model_resp = await client.get(
                f"{self.base_url}/models/{owner}/{name}",
                headers=self._headers(),
            )
            if model_resp.status_code >= 400:
                if model_resp.status_code == 404:
                    raise ReplicateHTTPError(
                        f"Replicate model not found: {owner}/{name}. "
                        f"Use a valid Replicate model slug (owner/name) or pin a version (owner/name:version)."
                    )
                raise ReplicateHTTPError(f"Replicate model lookup failed: {model_resp.status_code} {model_resp.text}")

            model_data = model_resp.json()
            latest = model_data.get("latest_version") or {}
            version_id = latest.get("id") or latest.get("version") or latest.get("uuid")
            if not version_id:
                raise ReplicateHTTPError("Replicate model lookup succeeded but no latest_version.id found.")

            resp2 = await client.post(
                f"{self.base_url}/predictions",
                headers=self._headers(),
                json={"version": version_id, "input": input},
            )
            if resp2.status_code >= 400:
                raise ReplicateHTTPError(f"Replicate create_prediction failed: {resp2.status_code} {resp2.text}")
            return resp2.json()

    async def get_prediction(self, prediction_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(
                f"{self.base_url}/predictions/{prediction_id}",
                headers=self._headers(),
            )
        if resp.status_code >= 400:
            raise ReplicateHTTPError(f"Replicate get_prediction failed: {resp.status_code} {resp.text}")
        return resp.json()

    async def wait_for_prediction(
        self,
        prediction_id: str,
        *,
        timeout_s: int,
        poll_interval_s: int,
        on_tick: Optional[Callable[[dict[str, Any], int], None]] = None,
    ) -> dict[str, Any]:
        start = time.monotonic()
        while True:
            pred = await self.get_prediction(prediction_id)
            elapsed = int(time.monotonic() - start)

            if on_tick:
                try:
                    on_tick(pred, elapsed)
                except Exception:
                    logger.debug("on_tick callback failed", exc_info=True)

            status = (pred.get("status") or "").lower()
            if status in {"succeeded", "failed", "canceled"}:
                return pred

            if elapsed >= timeout_s:
                raise ReplicateHTTPError(f"Replicate prediction timed out after {elapsed}s (id={prediction_id})")

            await asyncio.sleep(poll_interval_s)


def extract_first_output_url(output: Any) -> Optional[str]:
    """
    Replicate model outputs vary:
    - string URL
    - list[str] of URLs
    - list[dict] etc
    """
    if not output:
        return None

    if isinstance(output, str):
        return output

    if isinstance(output, list):
        if not output:
            return None
        first = output[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("url") or first.get("video") or first.get("image")

    if isinstance(output, dict):
        return output.get("url") or output.get("video") or output.get("image")

    return None


def _parse_model_identifier(model: str) -> tuple[str, str, Optional[str]]:
    raw = (model or "").strip()
    if not raw:
        raise ReplicateHTTPError("Empty model identifier.")

    base, version = (raw.split(":", 1) + [None])[:2]
    if "/" not in base:
        raise ReplicateHTTPError(
            f"Invalid model identifier '{raw}'. Expected 'owner/name' or 'owner/name:version'."
        )
    owner, name = base.split("/", 1)
    owner = owner.strip()
    name = name.strip()
    if not owner or not name:
        raise ReplicateHTTPError(
            f"Invalid model identifier '{raw}'. Expected 'owner/name' or 'owner/name:version'."
        )
    version = version.strip() if isinstance(version, str) and version.strip() else None
    return owner, name, version


