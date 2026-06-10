import importlib
import json

ROUTE_PREFIX = "/comfydex/live"
BRIDGE_ROUTES = [
    "status",
    "load_workflow",
    "reload_client",
    "reload_backend",
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
        self.runtime_module_name = runtime_module_name or f"{__package__}.runtime"
        self.runtime = importlib.import_module(self.runtime_module_name)

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

    @prompt_server.routes.post(f"{ROUTE_PREFIX}/rpc")
    async def comfydex_live_rpc(request):
        payload, error, status = await request_payload(request)
        if error:
            return json_response(web, error, status)
        result, status = await bridge.rpc(payload)
        return json_response(web, result, status)
