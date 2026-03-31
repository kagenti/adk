# Messaging & Streaming

Reference for Step 5 of the kagenti-adk-ui skill.

## Official Documentation

Read [User Messages](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/user-messages.mdx) and [A2A Client](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/a2a-client.mdx) before proceeding.

## Sending Messages

Send messages using the A2A client's `sendMessageStream` method. Always use streaming — even for single-turn agents — to handle status updates.

### Message Structure

A user message requires these fields:

| Field | Value | Purpose |
| --- | --- | --- |
| `kind` | `'message'` | Identifies this as a message (not a task status) |
| `role` | `'user'` | Marks the message as user-originated |
| `messageId` | `crypto.randomUUID()` | Unique identifier for this message |
| `contextId` | From session | Links message to the active session context |
| `parts` | `Part[]` | Message content (text, file, data parts) |
| `metadata` | From `resolveMetadata()` | Agent demand fulfillments and user response metadata |

### Message Parts

Messages can contain multiple parts of different kinds:

| Part Kind | Structure | Use Case |
| --- | --- | --- |
| `text` | `{ kind: 'text', text: string }` | Plain text input |
| `file` | `{ kind: 'file', file: { uri, name, mimeType } }` | File attachments |
| `data` | `{ kind: 'data', data: Record<string, unknown> }` | Structured data |

See [`client.ts`](https://github.com/kagenti/adk/blob/main/apps/adk-ts/examples/chat-ui/src/client.ts) (`sendMessage` function) for the reference implementation of message sending and stream processing.

## Processing the Stream

The stream yields events of three kinds: `status-update`, `message`, and `artifact-update`.

For each event:
- **`status-update`**: May contain a partial message with text. Also check with `handleTaskStatusUpdate(event)` if the agent needs user interaction (forms, approvals, etc.).
- **`message`**: The final agent response. Extract text with `extractTextFromMessage(message)`.
- **`artifact-update`**: The agent generated a file or data artifact.

### Required SDK Functions

| Function | Import | Purpose |
| --- | --- | --- |
| `extractTextFromMessage` | `@kagenti/adk` | Safely extract text from a multipart message |
| `handleTaskStatusUpdate` | `@kagenti/adk` | Parse status updates into typed interaction requests |
| `TaskStatusUpdateType` | `@kagenti/adk` | Enum of interaction types the agent may request |

## `handleTaskStatusUpdate` Returns

Returns an array of typed update objects indicating what the UI must do:

| `type` | Meaning | Required UI Action |
| --- | --- | --- |
| `FormRequired` | Agent needs form submission | Render form fields, submit values via `resolveUserMetadata` |
| `SecretRequired` | Agent needs secret values | Show secret input UI, submit via message metadata |
| `OAuthRequired` | Agent needs OAuth callback | Redirect to OAuth URL, handle callback |
| `ApprovalRequired` | Agent needs user approval | Show approval request, submit decision |
| `TextInputRequired` | Agent needs free-text input | Show text input, send as new message |

> [!WARNING]
> You MUST handle all `TaskStatusUpdateType` variants (C10). For types your UI does not fully support, show a clear message explaining the agent's request cannot be fulfilled.

## Metadata on Follow-Up Messages

The `metadata` from the initial `resolveMetadata()` call must be included on **every** message sent to the agent. This ensures the agent receives its demand fulfillments on each turn.

For follow-up messages that include user responses (form submissions, approvals), merge the additional metadata from `resolveUserMetadata()` with the session metadata. See the [User Messages documentation](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/user-messages.mdx) for the exact merge pattern.

## Streaming Text Accumulation

For UIs that show streaming text (typewriter effect), accumulate text from intermediate `status-update` events as they arrive rather than waiting for the final `message` event.

For the Streaming UI extension (text patches), see [references/ui-extensions.md](ui-extensions.md).

## Canceling a Task

If the user cancels a pending request, use `client.cancelTask({ taskId })`. This sends a cancellation signal to the agent and the stream will end with a canceled status.

## Anti-Patterns

- Never use `client.sendMessage()` (non-streaming). Always use `sendMessageStream()` to handle intermediate status updates.
- Never ignore `status-update` events. They may require user interaction (forms, approvals) to continue.
- Never drop the `metadata` field from messages. Without it, the agent cannot access its LLM, secrets, or other demand fulfillments.
- Never accumulate all events and process them after the stream ends. Process events as they arrive for responsive UI.
- Never assume the stream always succeeds. Wrap the stream loop in try/catch for network and protocol errors.
