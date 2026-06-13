# Conversational Workflow System

Comfydex `2.0.0` is the first ordinary-user conversational workflow system release.

## First-Class Scenarios

The 2.0 first-class scenarios are text-to-image, image-to-image, portrait, character consistency, product image, ControlNet, inpainting, upscaling, and background replacement.

## How Codex Uses It

Codex reads the Scenario Recipe Registry, plans a workflow from natural language, reports missing models or images, builds a readable ComfyUI UI workflow, and can use Live Bridge to push the generated graph to the ComfyUI canvas when the bridge is available.

The workflow plan keeps technical details available for advanced users while ordinary users can rely on presets, selected recipe names, missing requirement summaries, and plain-language guidance.

## Safety Boundary

Comfydex performs no automatic downloads and no automatic custom node installation. Missing models or nodes are reported through capability reports and install plans that require confirmation and audit records.

Generated UI workflows are meant for ComfyUI canvas review and editing. API submission still requires validation against live ComfyUI node metadata and the submit policy must be `allowed`.

## Readiness

The 2.0 Readiness Gate returns `ready_for_2_0` for this release. That status means all first-class scenarios have at least one ready recipe, supported semantic coverage, and a valid generated UI graph dry run.
