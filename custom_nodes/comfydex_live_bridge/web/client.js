const FRONTEND_STATUS_PATH = "/comfydex/live/frontend_status";
const WORKFLOW_RESULT_PATH = "/comfydex/live/workflow_result";
const HEARTBEAT_INTERVAL_MS = 5000;

function isCurrentWorkflowDirty(app) {
  const titleDirty = document.title.includes("*Unsaved");
  const extensionDirty = app?.extensionManager?.workflow?.isModified?.();
  const workflowDirty = app?.workflowManager?.activeWorkflow?.isModified?.();

  return Boolean(titleDirty || extensionDirty || workflowDirty);
}

async function postJson(api, path, payload) {
  const options = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
  const response =
    typeof api.fetchApi === "function"
      ? await api.fetchApi(path, options)
      : await fetch(path, options);

  if (!response.ok) {
    throw new Error(`POST ${path} failed with HTTP ${response.status}`);
  }

  try {
    return await response.json();
  } catch (_error) {
    return null;
  }
}

async function postHeartbeat({ api, version, clientId, lastError, notify }) {
  try {
    await postJson(api, FRONTEND_STATUS_PATH, {
      version,
      client_id: clientId,
      last_error: lastError,
    });
  } catch (error) {
    notify(`Failed to post heartbeat: ${error?.message || error}`, "error");
  }
}

async function postWorkflowResult({ api, notify }, result) {
  if (!result?.request_id) {
    return;
  }

  try {
    await postJson(api, WORKFLOW_RESULT_PATH, result);
  } catch (error) {
    notify(
      `Failed to post workflow result: ${error?.message || error}`,
      "error",
    );
  }
}

async function loadWorkflowIntoCanvas({ app, api, notify }, payload) {
  const workflow = payload?.workflow;
  const name = payload?.name || "Comfydex Workflow";
  const force = payload?.force === true;
  const request_id = payload?.request_id;

  if (!workflow || typeof workflow !== "object") {
    notify("Ignored load request without a workflow object.", "error");
    await postWorkflowResult(
      { api, notify },
      {
        request_id,
        ok: false,
        error: "invalid_workflow",
        message: "Load request did not include a workflow object.",
        name,
      },
    );
    return;
  }

  if (isCurrentWorkflowDirty(app) && !force) {
    const message = "Current ComfyUI canvas has unsaved changes.";
    notify(
      "Refused to load workflow because the current canvas is unsaved.",
      "error",
    );
    await postWorkflowResult(
      { api, notify },
      {
        request_id,
        ok: false,
        error: "unsaved_canvas",
        message,
        name,
      },
    );
    return;
  }

  try {
    if (typeof app.loadGraphData === "function") {
      await app.loadGraphData(workflow, true, true, name);
    } else if (app.graph?.configure) {
      app.graph.clear();
      app.graph.configure(workflow);
      app.canvas?.setDirty?.(true, true);
      app.canvas?.fitView?.();
    } else {
      throw new Error("No known ComfyUI graph loading API is available.");
    }

    document.title = `ComfyUI - ${name}`;
    notify(`Loaded workflow: ${name}`);
    await postWorkflowResult({ api, notify }, { request_id, ok: true, name });
  } catch (error) {
    const message = String(error?.message || error);
    notify(`Failed to load workflow: ${message}`, "error");
    await postWorkflowResult(
      { api, notify },
      {
        request_id,
        ok: false,
        error: "load_failed",
        message,
        name,
      },
    );
  }
}

export async function setup({ app, api, notify, version }) {
  const clientId = `client-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  let lastError = null;

  const heartbeat = () => {
    postHeartbeat({ api, version, clientId, lastError, notify });
  };

  const onLoadWorkflow = (event) => {
    loadWorkflowIntoCanvas({ app, api, notify }, event.detail).catch((error) => {
      lastError = String(error?.message || error);
      notify(`Unhandled workflow load error: ${lastError}`, "error");
    });
  };

  api.addEventListener("comfydex_live_load_workflow", onLoadWorkflow);
  heartbeat();
  const heartbeatInterval = setInterval(heartbeat, HEARTBEAT_INTERVAL_MS);

  return {
    dispose() {
      clearInterval(heartbeatInterval);
      api.removeEventListener("comfydex_live_load_workflow", onLoadWorkflow);
    },
  };
}
