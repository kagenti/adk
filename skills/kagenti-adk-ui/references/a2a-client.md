# A2A Client & Agent Requirements

Reference for Step 4 of the kagenti-adk-ui skill.

## Official Documentation

Read [A2A Client](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/a2a-client.mdx) and [Agent Requirements](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/agent-requirements.mdx) before proceeding.

## Creating the A2A Client

The A2A client communicates directly with the agent via the JSON-RPC protocol. Creating it requires:

1. A `ContextToken` from the platform API (Step 2).
2. `createAuthenticatedFetch(contextToken.token)` to wrap fetch with Bearer auth.
3. `ClientFactory` from `@a2a-js/sdk/client` configured with `JsonRpcTransportFactory` and `DefaultAgentCardResolver`, both using the authenticated fetch.
4. `getAgentCardPath(providerId)` from `@kagenti/adk` to get the correct agent card endpoint.
5. `factory.createFromUrl(baseUrl, agentCardPath)` to create the connected client.

See [`client.ts`](https://github.com/kagenti/adk/blob/main/apps/adk-ts/examples/chat-ui/src/client.ts) for the full reference implementation of client creation.

### Key Points

- `createAuthenticatedFetch(token)` wraps `fetch` with a `Bearer` token header. Use this for **all** authenticated requests.
- `getAgentCardPath(providerId)` returns the correct path to the agent's card endpoint.
- `factory.createFromUrl()` fetches the agent card and creates a fully configured client.

## Resolving Agent Requirements (Demands)

Agents declare their requirements (LLM, embedding, secrets, etc.) in their agent card. The UI must resolve these into fulfillments.

The flow is:
1. `client.getAgentCard()` — fetch the agent's capabilities.
2. `handleAgentCard(agentCard)` — returns `{ resolveMetadata, demands }`.
3. Inspect `demands` to determine what the agent needs.
4. `resolveMetadata({ llm: llmResolver, ... })` — resolve demands into message metadata.

### `handleAgentCard` Returns

| Property | Type | Purpose |
| --- | --- | --- |
| `resolveMetadata` | `(fulfillments: Fulfillments) => Promise<Record<string, unknown>>` | Resolves all demands into message metadata |
| `demands` | `{ llmDemands?, embeddingDemands?, mcpDemands?, oauthDemands?, secretDemands?, formDemands?, settingsDemands? }` | Extracted demands for inspection |

### Inspecting Demands

Use `demands` to determine what the agent requires before deciding which resolvers to provide. If a demand is present and no resolver is given, the agent will fail at runtime.

### LLM Model Selection (Required)

When an agent has LLM demands (`demands.llmDemands`), the UI **must** present a model selector so the user can choose which model to use. This is a core part of the ADK platform — do not silently auto-select or skip model selection.

**Flow:**

1. After fetching the agent card, inspect `demands.llmDemands.llm_demands` — a record of demand keys to demand objects (each with optional `suggested` model names).
2. For each demand, call `api.matchModelProviders({ suggested_models, capability: ModelCapability.Llm, score_cutoff: 0.4 })` to discover available models on the platform.
3. Render a model selector UI showing matched models for each demand, with the first match pre-selected as the default.
4. After the user confirms their selection, build LLM fulfillments using the **LLM proxy pattern**:

```typescript
llm_fulfillments[demandKey] = {
  identifier: 'llm_proxy',
  api_base: '{platform_url}/api/v1/openai/',
  api_key: contextToken.token,
  api_model: selectedModel,  // user-selected model ID
};
```

5. Pass the LLM fulfillment resolver to `resolveMetadata({ llm: resolver })`.

See [`build-fulfillments.ts`](https://github.com/kagenti/adk/blob/main/apps/adk-ui/src/modules/runs/contexts/agent-demands/build-fulfillments.ts) for the reference implementation. The same pattern applies to embedding demands using `identifier: 'embedding_proxy'`.

> [!WARNING]
> Do not use `buildLLMExtensionFulfillmentResolver()` — it requires pre-configured model providers and does not allow user model selection. Use the manual LLM proxy pattern described above.

### Other Fulfillment Resolvers

| Demand Type | Resolver Pattern | When Needed |
| --- | --- | --- |
| LLM | LLM proxy pattern with `matchModelProviders` + user selection (see above) | Agent requires LLM access |
| Embedding | Same proxy pattern with `ModelCapability.Embedding` | Agent requires embedding access |
| OAuth | Custom resolver returning `OAuthFulfillments` with `redirect_uri` | Agent requires OAuth |
| Secrets | Custom resolver returning `SecretFulfillments` | Agent requires pre-configured secrets |
| Form | Custom resolver returning `FormFulfillments` | Agent has initial form demands |

## Session Pattern

Combine context creation, token creation, client setup, and metadata resolution into a single session initialization function. The session should contain the A2A `client`, the `contextId`, and the resolved `metadata`.

The `metadata` object is attached to every outbound message so the agent receives its fulfilled demands.

See [`client.ts`](https://github.com/kagenti/adk/blob/main/apps/adk-ts/examples/chat-ui/src/client.ts) (`ensureSession` and `useAgent`) for the reference implementation of session management.

## Anti-Patterns

- Never create the A2A client without `createAuthenticatedFetch`. Unauthenticated clients cannot communicate with platform-proxied agents.
- Never cache or reuse `metadata` across sessions. Each session must resolve its own metadata.
- Never skip `handleAgentCard()`. Manually constructing metadata will miss agent demands and break the fulfillment contract.
- Never ignore unresolved demands. If the agent demands LLM and no resolver is provided, the agent will fail at runtime.
