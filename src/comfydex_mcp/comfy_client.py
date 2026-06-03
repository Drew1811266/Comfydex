from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx


class ComfyClient:
    def __init__(
        self, base_url: str, headers: dict[str, str], timeout_seconds: int
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = headers
        self.timeout_seconds = timeout_seconds
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "ComfyClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout_seconds,
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client is not None:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("ComfyClient must be used as an async context manager")
        return self._client

    async def check_connection(self) -> dict[str, Any]:
        try:
            response = await self.client.get("/system_stats")
            response.raise_for_status()
            return {
                "reachable": True,
                "base_url": self.base_url,
                "status_code": response.status_code,
                "system_stats": response.json(),
            }
        except httpx.HTTPError as exc:
            error_type = exc.__class__.__name__
            return {
                "reachable": False,
                "base_url": self.base_url,
                "error_type": error_type,
                "error": str(exc) or error_type,
            }

    async def get_object_info(self) -> dict[str, Any]:
        response = await self.client.get("/object_info")
        response.raise_for_status()
        return response.json()

    async def submit_prompt(
        self, workflow: dict[str, Any], client_id: str | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"prompt": workflow}
        if client_id:
            payload["client_id"] = client_id
        response = await self.client.post("/prompt", json=payload)
        response.raise_for_status()
        return response.json()

    async def get_queue(self) -> dict[str, Any]:
        response = await self.client.get("/queue")
        response.raise_for_status()
        return response.json()

    async def get_history(self, prompt_id: str | None = None) -> dict[str, Any]:
        path = f"/history/{prompt_id}" if prompt_id else "/history"
        response = await self.client.get(path)
        response.raise_for_status()
        return response.json()

    async def download_output(self, ref: dict[str, Any], target: Path) -> Path:
        params = {
            "filename": ref["filename"],
            "subfolder": ref.get("subfolder", ""),
            "type": ref.get("type", "output"),
        }
        response = await self.client.get("/view", params=params)
        response.raise_for_status()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
        return target


def extract_output_refs(history: dict[str, Any], prompt_id: str) -> list[dict[str, Any]]:
    prompt_history = history.get(prompt_id, history)
    outputs = prompt_history.get("outputs", {}) if isinstance(prompt_history, dict) else {}
    refs: list[dict[str, Any]] = []
    for node_output in outputs.values():
        if not isinstance(node_output, dict):
            continue
        for kind, values in node_output.items():
            if kind not in {"images", "gifs", "videos"} or not isinstance(values, list):
                continue
            for value in values:
                if isinstance(value, dict) and "filename" in value:
                    refs.append(
                        {
                            "filename": value["filename"],
                            "subfolder": value.get("subfolder", ""),
                            "type": value.get("type", "output"),
                            "kind": kind,
                        }
                    )
    return refs
