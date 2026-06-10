import importlib
import json
import time
from datetime import datetime, timezone

ROUTE_PREFIX = "/comfydex/live"
BRIDGE_VERSION = "1.2.0"
FRONTEND_STALE_SECONDS = 15
BRIDGE_ROUTES = [
    "status",
    "load_workflow",
    "reload_client",
    "reload_backend",
    "frontend_status",
    "workflow_result",
]


def json_response(web, payload, status=200):
    return web.Response(
        text=json.dumps(payload, ensure_ascii=False),
        status=status,
        content_type="application/json",
    )


async def request_payload(request):
    try:
        payload = await request.json()
    except Exception:
        return None, {"ok": False, "error": "invalid_json"}, 400

    if not isinstance(payload, dict):
        return None, {"ok": False, "error": "json_body_must_be_object"}, 400

    return payload, None, 200


class LiveBridgeBackend:
    def __init__(self, prompt_server, runtime_module_name=None):
        self.prompt_server = prompt_server
        self.generation = 0
        self.routes = list(BRIDGE_ROUTES)
        self.bridge_version = BRIDGE_VERSION
        self.frontend_stale_seconds = FRONTEND_STALE_SECONDS
        self.frontend = {
            "connected": False,
            "stale": True,
            "version": None,
            "client_id": None,
            "last_seen_at": None,
            "last_seen_monotonic": None,
            "last_error": None,
        }
        self.last_workflow_result = None
        self.pending_workflow_request_ids = set()
        self.workflow_request_counter = 0
        self.runtime_module_name = runtime_module_name or f"{__package__}.runtime"
        self.runtime = importlib.import_module(self.runtime_module_name)

    def next_workflow_request_id(self):
        self.workflow_request_counter += 1
        request_id = f"live-{self.workflow_request_counter}"
        self.pending_workflow_request_ids.add(request_id)
        return request_id

    def record_frontend_status(self, payload):
        self.frontend.update(
            {
                "version": payload.get("version"),
                "client_id": payload.get("client_id"),
                "last_error": payload.get("last_error"),
                "last_seen_at": datetime.now(timezone.utc).isoformat(),
                "last_seen_monotonic": time.monotonic(),
            }
        )
        return self.frontend_status_snapshot()

    def frontend_status_snapshot(self):
        last_seen_monotonic = self.frontend.get("last_seen_monotonic")
        age_ms = None
        if last_seen_monotonic is not None:
            age_ms = max(0, int((time.monotonic() - last_seen_monotonic) * 1000))

        stale = age_ms is None or age_ms > self.frontend_stale_seconds * 1000
        connected = last_seen_monotonic is not None and not stale
        self.frontend["connected"] = connected
        self.frontend["stale"] = stale

        return {
            "connected": connected,
            "stale": stale,
            "version": self.frontend.get("version"),
            "client_id": self.frontend.get("client_id"),
            "last_seen_at": self.frontend.get("last_seen_at"),
            "last_seen_age_ms": age_ms,
            "last_error": self.frontend.get("last_error"),
        }

    async def status(self, _payload):
        return await self.runtime.status(self, _payload)

    async def load_workflow(self, payload):
        return await self.runtime.load_workflow(self, payload)

    async def reload_client(self, payload):
        return await self.runtime.reload_client(self, payload)

    async def reload_backend(self, _payload):
        importlib.invalidate_caches()
        try:
            reloaded_runtime = importlib.reload(self.runtime)
        except Exception as error:
            return {
                "ok": False,
                "error": "backend_reload_failed",
                "message": str(error),
                "generation": self.generation,
            }, 500

        self.generation += 1
        self.runtime = reloaded_runtime
        return await self.runtime.reload_backend(self, _payload)

    async def frontend_status(self, payload):
        return await self.runtime.frontend_status(self, payload)

    async def workflow_result(self, payload):
        return await self.runtime.workflow_result(self, payload)

    async def rpc(self, payload):
        action = payload.get("action")
        rpc_payload = payload.get("payload") or {}

        if action == "status":
            return await self.status(rpc_payload)
        if action == "load_workflow":
            return await self.load_workflow(rpc_payload)
        if action == "reload_client":
            return await self.reload_client(rpc_payload)
        if action == "reload_backend":
            return await self.reload_backend(rpc_payload)
        if action == "frontend_status":
            return await self.frontend_status(rpc_payload)
        if action == "workflow_result":
            return await self.workflow_result(rpc_payload)

        return {"ok": False, "error": "unknown_action", "action": action}, 404


def register_routes(prompt_server):
    from aiohttp import web

    bridge = LiveBridgeBackend(prompt_server)

    @prompt_server.routes.get(f"{ROUTE_PREFIX}/status")
    async def comfydex_live_status(_request):
        payload, status = await bridge.status({})
        return json_response(web, payload, status)

    @prompt_server.routes.post(f"{ROUTE_PREFIX}/load_workflow")
    async def comfydex_live_load_workflow(request):
        payload, error, status = await request_payload(request)
        if error:
            return json_response(web, error, status)
        result, status = await bridge.load_workflow(payload)
        return json_response(web, result, status)

    @prompt_server.routes.post(f"{ROUTE_PREFIX}/reload_client")
    async def comfydex_live_reload_client(request):
        payload, error, status = await request_payload(request)
        if error:
            return json_response(web, error, status)
        result, status = await bridge.reload_client(payload)
        return json_response(web, result, status)

    @prompt_server.routes.post(f"{ROUTE_PREFIX}/reload_backend")
    async def comfydex_live_reload_backend(request):
        payload, error, status = await request_payload(request)
        if error:
            return json_response(web, error, status)
        result, status = await bridge.reload_backend(payload)
        return json_response(web, result, status)

    @prompt_server.routes.post(f"{ROUTE_PREFIX}/frontend_status")
    async def comfydex_live_frontend_status(request):
        payload, error, status = await request_payload(request)
        if error:
            return json_response(web, error, status)
        result, status = await bridge.frontend_status(payload)
        return json_response(web, result, status)

    @prompt_server.routes.post(f"{ROUTE_PREFIX}/workflow_result")
    async def comfydex_live_workflow_result(request):
        payload, error, status = await request_payload(request)
        if error:
            return json_response(web, error, status)
        result, status = await bridge.workflow_result(payload)
        return json_response(web, result, status)

    @prompt_server.routes.post(f"{ROUTE_PREFIX}/rpc")
    async def comfydex_live_rpc(request):
        payload, error, status = await request_payload(request)
        if error:
            return json_response(web, error, status)
        result, status = await bridge.rpc(payload)
        return json_response(web, result, status)
