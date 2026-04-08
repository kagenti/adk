# A2A Client & Agent Requirements

Reference for Step 4 of the kagenti-adk-ui skill.

## Official Documentation

Read [A2A Client](https://raw.githubusercontent.com/kagenti/adk/main/docs/development/custom-ui/a2a-client.mdx) and [Agent Requirements](https://raw.githubusercontent.com/kagenti/adk/main/docs/development/custom-ui/agent-requirements.mdx) before proceeding.

## Creating the A2A Client

Use `buildAgentClient` from `@kagenti/adk` to create a fully configured A2A client. It handles authenticated fetch, agent card fetching, extension discovery, and JSON-RPC + SSE transport setup. For lower-level control, use `createA2AClient` + `fetchAgentCard` directly.

See [`client.ts`](https://raw.githubusercontent.com/kagenti/adk/main/apps/adk-ts/examples/chat-ui/src/client.ts) for the full reference implementation and [Getting Started § 4](https://raw.githubusercontent.com/kagenti/adk/main/docs/development/custom-ui/getting-started.mdx) for the usage pattern.

### Key Points

- `buildAgentClient` uses `createAuthenticatedFetch` internally to attach the `Authorization` header.
- No need to install or use `@a2a-js/sdk` for the A2A transport — the SDK provides it built-in.
- `eventsource-parser` is an optional peer dependency required for streaming (install it alongside `@kagenti/adk`).

## Resolving Agent Requirements (Demands)

Agents declare their requirements (LLM, embedding, secrets, etc.) in their agent card. The UI must resolve these into fulfillments.

The flow is:

1. `client.getAgentCard()` — fetch the agent's capabilities.
2. `handleAgentCard(agentCard)` — returns `{ resolveMetadata, demands }`.
3. Inspect `demands` to determine what the agent needs.
4. `resolveMetadata({ llm: llmResolver, ... })` — resolve demands into message metadata.

See [A2A Client § 1](https://raw.githubusercontent.com/kagenti/adk/main/docs/development/custom-ui/a2a-client.mdx) for the full demand resolution pattern.

### `handleAgentCard` Returns

| Property          | Type                                                                                                             | Purpose                                    |
| ----------------- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| `resolveMetadata` | `(fulfillments: Fulfillments) => Promise<Record<string, unknown>>`                                               | Resolves all demands into message metadata |
| `demands`         | `{ llmDemands?, embeddingDemands?, mcpDemands?, oauthDemands?, secretDemands?, formDemands?, settingsDemands? }` | Extracted demands for inspection           |

### Inspecting Demands

Use `demands` to determine what the agent requires before deciding which resolvers to provide. If a demand is present and no resolver is given, the agent will fail at runtime.

### LLM Model Selection (Required)

When an agent has LLM demands (`demands.llmDemands`), the UI **must** present a model selector so the user can choose which model to use. This is a core part of the ADK platform — do not silently auto-select or skip model selection.

**Flow:**

1. After fetching the agent card, inspect `demands.llmDemands.llm_demands` — a record of demand keys to demand objects (each with optional `suggested` model names).
2. For each demand, call `api.matchModelProviders(...)` to discover available models on the platform.
3. Render a model selector UI showing matched models for each demand, with the first match pre-selected as the default.
4. After the user confirms their selection, build LLM fulfillments using the **LLM proxy pattern** — see [A2A Client § 1](https://raw.githubusercontent.com/kagenti/adk/main/docs/development/custom-ui/a2a-client.mdx) for the exact shape.
5. Pass the LLM fulfillment resolver to `resolveMetadata({ llm: resolver })`.

For a simpler approach, use `buildLLMExtensionFulfillmentResolver(api, contextToken)` which handles model matching and fulfillment automatically — see [Agent Requirements § LLM](https://raw.githubusercontent.com/kagenti/adk/main/docs/development/custom-ui/agent-requirements.mdx). For full control over model selection UI, see [`build-fulfillments.ts`](https://raw.githubusercontent.com/kagenti/adk/main/apps/adk-ui/src/modules/runs/contexts/agent-demands/build-fulfillments.ts) for the manual pattern.

### Other Fulfillment Resolvers

| Demand Type | Resolver Pattern                                                          | When Needed                           |
| ----------- | ------------------------------------------------------------------------- | ------------------------------------- |
| LLM         | LLM proxy pattern with `matchModelProviders` + user selection (see above) | Agent requires LLM access             |
| Embedding   | Same proxy pattern with `ModelCapability.Embedding`                       | Agent requires embedding access       |
| OAuth       | Custom resolver returning `OAuthFulfillments` with `redirect_uri`         | Agent requires OAuth                  |
| Secrets     | Custom resolver returning `SecretFulfillments`                            | Agent requires pre-configured secrets |
| Form        | Custom resolver returning `FormFulfillments`                              | Agent has initial form demands        |

## Session Pattern

Combine context creation, token creation, client setup, and metadata resolution into a single session initialization function. The session should contain the A2A `client`, the `contextId`, and the resolved `metadata`.

The `metadata` object is attached to every outbound message so the agent receives its fulfilled demands.

See [`client.ts`](https://raw.githubusercontent.com/kagenti/adk/main/apps/adk-ts/examples/chat-ui/src/client.ts) (`ensureSession` and `useAgent`) for the reference implementation of session management.

## Anti-Patterns

- Never ignore unresolved demands. If the agent demands LLM and no resolver is provided, the agent will fail at runtime.
