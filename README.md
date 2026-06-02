# Comfydex

Comfydex is a Codex plugin that connects Codex to a configured ComfyUI server.

Default ComfyUI URL:

```text
http://127.0.0.1:8188
```

Default workspace data directories:

```text
workflows/
runs/
```

Local development:

```powershell
python -m pip install -e "C:/Users/Drew/plugins/comfydex[dev]"
python -m pytest
python "C:/Users/Drew/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py" "C:/Users/Drew/plugins/comfydex"
```

## Verification

Run the full local verification suite:

```powershell
Set-Location "C:/Users/Drew/plugins/comfydex"
python -m pytest -v
python "C:/Users/Drew/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py" "C:/Users/Drew/plugins/comfydex"
```

Run a manual connection check from a Codex workspace:

```powershell
Set-Location "D:/Software Project/Comfydex"
python "C:/Users/Drew/plugins/comfydex/scripts/smoke_check.py"
```

Install or refresh the plugin from the default personal marketplace:

```powershell
codex plugin add comfydex@personal
```

Start a new Codex thread after reinstalling so Codex can discover updated Skills and MCP tools.
