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
