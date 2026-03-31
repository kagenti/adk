# Interactive Features

Reference for Step 7 of the kagenti-adk-ui skill.

## Official Documentation

Read [A2A Client](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/a2a-client.mdx) and [Agent Requirements](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/agent-requirements.mdx) before proceeding.

## Overview

Agents may pause execution and request user interaction via task status updates. The UI must detect these requests, render the appropriate input interface, and submit the user's response.

All interactive feature detection flows through `handleTaskStatusUpdate()` from `@kagenti/adk`. Process each `status-update` event from the stream and route by `update.type`.

---

## Forms

### Detection

`TaskStatusUpdateType.FormRequired` — the agent requests structured input via a form.

### Form Data Structure

The form request contains a `FormRender` object with a `fields` array. Each field has a `type` discriminator.

### Field Types

| Type | `type` Value | Key Properties |
| --- | --- | --- |
| Text | `'text'` | `id`, `label`, `required?`, `default?`, `description?` |
| Date | `'date'` | `id`, `label`, `required?` |
| File | `'file'` | `id`, `label`, `required?`, `accept?` (MIME types) |
| Single Select | `'select'` | `id`, `label`, `options: SelectFieldOption[]`, `required?` |
| Multi Select | `'multi-select'` | `id`, `label`, `options: SelectFieldOption[]`, `required?` |
| Checkbox | `'checkbox'` | `id`, `label`, `required?`, `default?` |
| Checkbox Group | `'checkbox-group'` | `id`, `label`, `options: SelectFieldOption[]`, `required?` |

For exact type definitions, inspect `FormField` and related types from `@kagenti/adk/extensions`. See the [Agent Requirements documentation](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/agent-requirements.mdx) for form handling details.

### Rendering

Dynamically render form fields based on the `type` discriminator. Map each field type to the appropriate input element for your UI framework.

### Submitting Form Responses

Collect values keyed by field `id` and submit using `resolveUserMetadata({ form: formValues })` from `@kagenti/adk`. Merge the result with session metadata and send as a new message.

> [!WARNING]
> Form field `id` values in the submission **must exactly match** the field `id` values from the `FormRender`. Mismatched IDs cause silent parse failures on the agent side.

---

## Approvals

### Detection

`TaskStatusUpdateType.ApprovalRequired` — the agent requests user approval for an action.

### Approval Request Structure

The request is either a `GenericApprovalRequest` (general prompt) or `ToolCallApprovalRequest` (specific tool execution with tool name and parameters).

### Rendering

Show the approval request description and provide Approve/Reject controls.

### Submitting Approval Responses

Use `resolveUserMetadata({ approvalResponse: { decision, requestId } })`. The `ApprovalDecision` enum from `@kagenti/adk` provides `Approve` and `Reject` values.

---

## OAuth

### Detection

`TaskStatusUpdateType.OAuthRequired` — the agent needs an OAuth authorization flow.

### Handling

1. Extract the `authorization_endpoint_url` from the update data.
2. Redirect the user to the OAuth URL (or open in a popup).
3. Handle the callback redirect URI.
4. Submit the redirect URI back to the agent via message metadata.

---

## Secrets

### Detection

`TaskStatusUpdateType.SecretRequired` — the agent needs secret values the user must provide.

### Handling

1. Extract the secret demands (field names and descriptions).
2. Render a secure input for each required secret.
3. Submit the secret values via message metadata.

> [!CAUTION]
> Secret values must never be logged, stored in state, or persisted to storage. Handle them only transiently for submission.

---

## Text Input Required

### Detection

`TaskStatusUpdateType.TextInputRequired` — the agent needs a free-text follow-up.

### Handling

The simplest case. Show a text input and send the response as a regular message with session metadata.

---

## File Uploads (via Forms)

If a form includes a `FileField`, the UI must handle file upload:

1. Render a file input with the field's `accept` MIME types.
2. Upload the file to the platform via `api.createFile()`.
3. Include the resulting file URI in the form response.

---

## Graceful Degradation (C10)

For any `TaskStatusUpdateType` the UI does not fully implement, display a clear message explaining the agent's request cannot be fulfilled. Never silently ignore an interaction request — the user must know the agent is waiting.

## Anti-Patterns

- Never hardcode form fields. Always render dynamically from the `FormRender` fields array.
- Never submit form values with different field IDs than those in the form request.
- Never skip validation for required form fields before submission.
- Never cache form responses across sessions.
- Never show a generic "loading" state when the agent is waiting for user interaction. Show the specific interaction UI.
