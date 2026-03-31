# UI Extensions

Reference for Step 8 of the kagenti-adk-ui skill.

## Official Documentation

Read [Agent Responses](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/agent-responses.mdx) and [Agent Requirements](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/agent-requirements.mdx) before proceeding.

## Overview

Agents emit UI extension metadata on messages and artifacts. The UI extracts this metadata to render rich features beyond plain text. Each extension has a URI, a data schema, and an extraction helper.

## Extracting Extension Data

Use `extractUiExtensionData` from `@kagenti/adk/core` with specific extension objects from `@kagenti/adk/extensions`. The general pattern: import the extension object, call `extractUiExtensionData(extension)(message.metadata)`, and check the result for presence before rendering.

For exact import paths and type signatures, inspect the installed `@kagenti/adk/extensions` package exports.

## Extension Selection Matrix

Trajectory is **always required**. Implement other extensions based on agent needs or user request.

| Extension | URI Suffix | Data Type | When to Implement | Documentation |
| --- | --- | --- | --- | --- |
| **Trajectory** | `ui/trajectory/v1` | `TrajectoryMetadata` | **Always (required)** | [Agent Responses](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/agent-responses.mdx) |
| **Citation** | `ui/citation/v1` | `CitationMetadata` | Agent provides source references | [Agent Responses](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/agent-responses.mdx) |
| **Streaming** | `ui/streaming/v1` | `StreamingMetadata` | Agent sends text patches for live streaming | [Agent Responses](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/agent-responses.mdx) |
| **Error** | `ui/error/v1` | `ErrorMetadata` | Agent reports structured errors | [Error Handling](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/error-handling.mdx) |
| **Canvas** | `ui/canvas/v1` | `CanvasEditRequest` | Agent provides editable documents | [Agent Requirements](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/agent-requirements.mdx) |
| **Agent Detail** | `agent-detail/v1` | `AgentDetail` | Display agent metadata (tools, author, mode) | [Agent Requirements](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/agent-requirements.mdx) |
| **Settings** | `ui/settings/v1` | `SettingsDemands` / `SettingsValues` | Agent exposes user-configurable settings | [Agent Requirements](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/agent-requirements.mdx) |

---

## Trajectory (Required)

Shows intermediate reasoning steps, tool calls, and progress. The trajectory data contains an array of entries, each with a `title`, `content`, and optional `group_id` for grouping related steps.

### Rendering Guidelines

- Show trajectory as a collapsible/expandable panel alongside the agent's response.
- Group trajectory entries by `group_id` when present.
- Display the `title` prominently and `content` as preformatted/code text.
- Trajectory is supplementary — never replace the agent's final response with trajectory content.

For the exact `TrajectoryMetadata` type shape, inspect the `trajectoryExtension` from `@kagenti/adk/extensions` and refer to the [Agent Responses documentation](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/agent-responses.mdx).

---

## Citations

Source references for agent responses. Citation data contains entries with `title`, optional `url`, and optional `snippet`.

### Rendering Guidelines

- Show citations as a numbered reference list below the agent's response.
- Link titles to URLs when present.
- Show snippets as supplementary context.

For the exact type shape, inspect the `citationExtension` from `@kagenti/adk/extensions`.

---

## Streaming (Text Patches)

Enables live text streaming with incremental patches. Process streaming metadata from `status-update` events as they arrive rather than waiting for the final message.

For the exact type shape, inspect the `streamingExtension` from `@kagenti/adk/extensions`.

---

## Error

Structured error information from the agent. Error data contains entries with `message`, optional `stacktrace`, and optional `context` dictionary.

### Rendering Guidelines

- Show the error message prominently.
- Stack traces should be hidden behind a collapsible toggle — never shown to end users by default.
- Context data can be rendered as a key-value table for diagnostics.

For the exact type shape, inspect the `errorExtension` from `@kagenti/adk/extensions` and refer to the [Error Handling documentation](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/error-handling.mdx).

---

## Canvas

Editable documents the agent can create and update. When the agent sends canvas content, render it in an editable area. When the user edits, submit changes via `resolveUserMetadata({ canvasEditRequest: ... })`.

For the exact type shape, inspect the `canvasExtension` from `@kagenti/adk/extensions`.

---

## Agent Detail

Metadata about the agent itself: interaction mode (`SingleTurn` / `MultiTurn`), available tools, author, and contributors. Use this to adapt the UI layout — e.g., a simple input form for single-turn agents vs. a full chat interface for multi-turn.

For the exact type shape, inspect the `agentDetailExtension` from `@kagenti/adk/extensions`.

---

## Settings

User-configurable agent settings. Extract settings demands from the agent card, render settings fields (checkboxes, selects) in a settings panel, and include settings values in message metadata via the fulfillment resolver.

For the exact type shape, inspect the `settingsExtension` from `@kagenti/adk/extensions`.

---

## Anti-Patterns

- Never render extension data without checking for its presence. Extensions are optional (except trajectory); always check before rendering.
- Never hardcode extension URIs. Use the SDK-provided extension objects and their extraction helpers.
- Never render trajectory content as the agent's final response. Trajectory is supplementary context, not the answer.
- Never render raw error stack traces to end users by default. Show behind a collapsible toggle.
- Never skip canvas edit acknowledgment. If the agent sends canvas content, the UI must provide editing capability.
