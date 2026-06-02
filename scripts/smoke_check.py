from __future__ import annotations

import asyncio
from pathlib import Path

from comfydex_mcp.comfy_client import ComfyClient
from comfydex_mcp.config import load_config, redact_config


async def main() -> None:
    workspace = Path.cwd()
    config = load_config(workspace)
    print("Comfydex config:")
    print(redact_config(config))
    async with ComfyClient(config.base_url, config.headers, config.request_timeout_seconds) as client:
        result = await client.check_connection()
    print("Connection result:")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
