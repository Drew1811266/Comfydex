from .backend import register_routes

WEB_DIRECTORY = "./web"
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

try:
    from server import PromptServer

    register_routes(PromptServer.instance)
except Exception as error:
    print(f"[Comfydex Live Bridge] Route registration skipped: {error}")
