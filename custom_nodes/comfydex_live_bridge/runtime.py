async def status(bridge, _payload):
    return {
        "ok": True,
        "bridge": "comfydex_live_bridge",
        "bridge_version": bridge.bridge_version,
        "generation": bridge.generation,
        "routes": list(bridge.routes),
        "frontend": bridge.frontend_status_snapshot(),
        "last_workflow_result": bridge.last_workflow_result,
    }, 200


async def load_workflow(bridge, payload):
    workflow = payload.get("workflow")
    name = payload.get("name") or "Comfydex Workflow"
    activate = payload.get("activate", True)
    force = payload.get("force", False)

    if not isinstance(workflow, dict):
        return {"ok": False, "error": "workflow_must_be_json_object"}, 400

    request_id = bridge.next_workflow_request_id()
    message = {
        "workflow": workflow,
        "request_id": request_id,
        "name": str(name),
        "activate": bool(activate),
        "force": bool(force),
    }
    bridge.prompt_server.send_sync("comfydex_live_load_workflow", message)

    return {
        "ok": True,
        "request_id": request_id,
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


async def frontend_status(bridge, payload):
    frontend = bridge.record_frontend_status(payload)
    return {"ok": True, "frontend": frontend}, 200


async def workflow_result(bridge, payload):
    request_id = payload.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        return {"ok": False, "error": "request_id_required"}, 400

    ok = payload.get("ok")
    if not isinstance(ok, bool):
        return {"ok": False, "error": "workflow_result_ok_must_be_boolean"}, 400

    result = {
        "request_id": request_id,
        "ok": ok,
    }
    for key in ("name", "error", "message"):
        value = payload.get(key)
        if isinstance(value, str):
            result[key] = value

    bridge.last_workflow_result = result
    return {"ok": True, "last_workflow_result": result}, 200
