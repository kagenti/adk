# Agent Responses

Reference for Step 6 of the kagenti-adk-ui skill.

## Official Documentation

Read [Agent Responses](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/agent-responses.mdx) before proceeding.

## Extracting Text from Messages

Always use `extractTextFromMessage(message)` from `@kagenti/adk` or iterate parts by `kind`. Never access `parts[0].text` directly — messages are multipart.

If you need more control, iterate parts and switch on `part.kind`:
- `'text'` — `part.text` contains plain text content.
- `'file'` — `part.file` contains `uri`, `name`, and `mimeType`.
- `'data'` — `part.data` contains arbitrary structured data (`Record<string, unknown>`).

See [`utils.ts`](https://github.com/kagenti/adk/blob/main/apps/adk-ts/examples/chat-ui/src/utils.ts) (`extractTextFromMessage` usage) for the reference pattern.

## Rendering File Parts

File parts use URIs that may be `adk://` scheme (platform-managed files) or `https://` (external).

For `adk://` URIs, resolve them through the platform API using `api.readFileContent()`. Never fetch `adk://` URIs directly as HTTP URLs.

See the [Manage Files documentation](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/agent-responses.mdx) for file resolution patterns.

## Processing Artifacts

Artifacts are generated content the agent produces (files, data exports). They arrive via `artifact-update` stream events. Artifacts have the same `parts` structure as messages (text, file, data) plus optional `name` and `metadata` fields.

### Artifact vs Message

| Aspect | Message | Artifact |
| --- | --- | --- |
| Purpose | Conversational response | Generated content output |
| Parts | Text, file, data | Text, file, data |
| Metadata | UI extension data | UI extension data |
| Typical content | Agent replies | Generated files, reports, structured output |

## Reading Extension Metadata

Agent messages and artifacts may include extension metadata for rich rendering (citations, trajectories, errors, etc.). Use `extractUiExtensionData` from `@kagenti/adk/core` with specific extension objects from `@kagenti/adk/extensions`.

See [references/ui-extensions.md](ui-extensions.md) for extraction patterns per extension.

## Anti-Patterns

- Never access `message.parts[0].text` without checking part kind. The first part may not be text.
- Never ignore file parts. If the agent sends files, the UI must provide download/preview capability.
- Never treat `adk://` URIs as directly fetchable HTTP URLs. They must be resolved through the platform API.
- Never skip artifacts. They represent generated content the user expects to access.
- Never render raw HTML from agent text without sanitization.
