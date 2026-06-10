import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

let activeClient = null;

function notify(message, type = "info") {
  console[type === "error" ? "error" : "log"](
    `[Comfydex Live Bridge] ${message}`,
  );
}

async function loadClient(version) {
  try {
    activeClient?.dispose?.();
    const module = await import(`./client.js?v=${version}`);
    activeClient = await module.setup({ app, api, notify, version });
    notify(`Client ready: ${version}`);
  } catch (error) {
    notify(`Failed to load client: ${error?.message || error}`, "error");
  }
}

app.registerExtension({
  name: "comfydex.live_bridge.loader",
  async setup() {
    api.addEventListener("comfydex_live_reload_client", (event) => {
      const version = event.detail?.version || String(Date.now());
      loadClient(version);
    });
    await loadClient("bootstrap");
  },
});
