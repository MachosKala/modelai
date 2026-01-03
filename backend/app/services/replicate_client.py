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

    async def create_prediction(self, *, model: str, input: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": model, "input": input}
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/predictions",
                headers=self._headers(),
                json=payload,
            )
        if resp.status_code >= 400:
            raise ReplicateHTTPError(f"Replicate create_prediction failed: {resp.status_code} {resp.text}")
        return resp.json()

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


