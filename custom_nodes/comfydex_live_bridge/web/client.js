function isCurrentWorkflowDirty(app) {
  const titleDirty = document.title.includes("*Unsaved");
  const extensionDirty = app?.extensionManager?.workflow?.isModified?.();
  const workflowDirty = app?.workflowManager?.activeWorkflow?.isModified?.();

  return Boolean(titleDirty || extensionDirty || workflowDirty);
}

async function loadWorkflowIntoCanvas({ app, notify }, payload) {
  const workflow = payload?.workflow;
  const name = payload?.name || "Comfydex Workflow";
  const force = payload?.force === true;

  if (!workflow || typeof workflow !== "object") {
    notify("Ignored load request without a workflow object.", "error");
    return;
  }

  if (isCurrentWorkflowDirty(app) && !force) {
    notify(
      "Refused to load workflow because the current canvas is unsaved.",
      "error",
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
  } catch (error) {
    notify(`Failed to load workflow: ${error?.message || error}`, "error");
  }
}

export async function setup({ app, api, notify }) {
  const onLoadWorkflow = (event) => {
    loadWorkflowIntoCanvas({ app, notify }, event.detail);
  };

  api.addEventListener("comfydex_live_load_workflow", onLoadWorkflow);

  return {
    dispose() {
      api.removeEventListener("comfydex_live_load_workflow", onLoadWorkflow);
    },
  };
}
