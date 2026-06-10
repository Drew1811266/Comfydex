async def status(bridge, _payload):
    return {
        "ok": True,
        "bridge": "comfydex_live_bridge",
        "routes": list(bridge.routes),
    }, 200


async def load_workflow(bridge, payload):
    workflow = payload.get("workflow")
    name = payload.get("name") or "Comfydex Workflow"
    activate = payload.get("activate", True)
    force = payload.get("force", False)

    if not isinstance(workflow, dict):
        return {"ok": False, "error": "workflow_must_be_json_object"}, 400

    message = {
        "workflow": workflow,
        "name": str(name),
        "activate": bool(activate),
        "force": bool(force),
    }
    bridge.prompt_server.send_sync("comfydex_live_load_workflow", message)

    return {
        "ok": True,
        "name": str(name),
        "activate": bool(activate),
        "force": bool(force),
    }, 200


async def reload_client(bridge, payload):
    version = str(payload.get("version") or bridge.generation)
    message = {"version": version}
    bridge.prompt_server.send_sync("comfydex_live_reload_client", message)
    return {"ok": True, "version": version}, 200


async def reload_backend(bridge, _payload):
    return {
        "ok": True,
        "generation": bridge.generation,
        "runtime": bridge.runtime.__name__,
    }, 200
