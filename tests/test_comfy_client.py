from pathlib import Path

import httpx
import pytest
import respx

from comfydex_mcp.comfy_client import ComfyClient, extract_output_refs


@pytest.mark.asyncio
@respx.mock
async def test_check_connection_calls_system_stats():
    respx.get("http://127.0.0.1:8188/system_stats").mock(
        return_value=httpx.Response(200, json={"system": {"os": "nt"}})
    )

    async with ComfyClient("http://127.0.0.1:8188", {}, 5) as client:
        result = await client.check_connection()

    assert result["reachable"] is True
    assert result["system_stats"] == {"system": {"os": "nt"}}


@pytest.mark.asyncio
@respx.mock
async def test_check_connection_reports_exception_type_when_error_message_is_empty():
    respx.get("http://127.0.0.1:8188/system_stats").mock(
        side_effect=httpx.ReadTimeout("")
    )

    async with ComfyClient("http://127.0.0.1:8188", {}, 5) as client:
        result = await client.check_connection()

    assert result["reachable"] is False
    assert result["error_type"] == "ReadTimeout"
    assert result["error"]


@pytest.mark.asyncio
@respx.mock
async def test_submit_prompt_returns_prompt_id():
    respx.post("http://127.0.0.1:8188/prompt").mock(
        return_value=httpx.Response(200, json={"prompt_id": "abc"})
    )

    async with ComfyClient(
        "http://127.0.0.1:8188", {"Authorization": "Bearer x"}, 5
    ) as client:
        result = await client.submit_prompt(
            {"1": {"class_type": "SaveImage", "inputs": {}}}, "client-1"
        )

    assert result == {"prompt_id": "abc"}


def test_extract_output_refs_from_history():
    history = {
        "abc": {
            "outputs": {
                "9": {
                    "images": [
                        {"filename": "a.png", "subfolder": "", "type": "output"}
                    ]
                }
            }
        }
    }

    refs = extract_output_refs(history, "abc")

    assert refs == [
        {"filename": "a.png", "subfolder": "", "type": "output", "kind": "images"}
    ]


@pytest.mark.asyncio
@respx.mock
async def test_download_output_writes_file(tmp_path: Path):
    respx.get("http://127.0.0.1:8188/view").mock(
        return_value=httpx.Response(200, content=b"png")
    )

    async with ComfyClient("http://127.0.0.1:8188", {}, 5) as client:
        target = await client.download_output(
            {"filename": "a.png", "subfolder": "", "type": "output"},
            tmp_path / "a.png",
        )

    assert target.read_bytes() == b"png"
