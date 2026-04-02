# Skill Findings & Corrections

Issues discovered while building a React + Vite chat UI using the kagenti-adk-ui skill.

---

## 1. A2A Client: Wrong approach (`references/a2a-client.md`)

**Severity: Major — causes build failures and runtime errors**

The doc instructs using `ClientFactory` from `@a2a-js/sdk/client` with `JsonRpcTransportFactory` and `DefaultAgentCardResolver`:

```typescript
// What the doc says (WRONG)
const factory = new ClientFactory({
  transportFactory: new JsonRpcTransportFactory({ fetch: authenticatedFetch }),
  agentCardResolver: new DefaultAgentCardResolver({ fetch: authenticatedFetch }),
});
const client = await factory.createFromUrl(baseUrl, agentCardPath);
```

**Problems:**
- The `ClientFactory` constructor takes `{ transports: TransportFactory[], cardResolver?: AgentCardResolver }` — not `transportFactory`/`agentCardResolver`. The property names and structure in the doc don't match the actual API.
- `JsonRpcTransportFactory` takes `{ fetchImpl?: typeof fetch }` — not `{ fetch }`.
- `Client.sendMessageStream()` from `@a2a-js/sdk` returns `AsyncGenerator<A2AStreamEventData>` which is a raw union of `Message | Task | TaskStatusUpdateEvent | TaskArtifactUpdateEvent`. This doesn't match the `StreamResponse` type from `@kagenti/adk` that uses `{ statusUpdate, message, artifactUpdate }` wrapper objects.
- `streamResponseSchema` from `@kagenti/adk` cannot validate events from the `@a2a-js/sdk` client because they have different shapes.

**What works:** A custom JSON-RPC client that POSTs to `/api/v1/a2a/{providerId}/` with `SendStreamingMessage` as the method, parses SSE events via `eventsource-parser`, and validates each event with `streamResponseSchema.parse(data.result)`. This is what the reference chat-ui implementation does.

**Fix:** Replace `ClientFactory` instructions with the custom JSON-RPC + SSE pattern. Explain the endpoint URL pattern. Add `eventsource-parser` to required dependencies.

---

## 2. Missing dependency: `eventsource-parser` (`references/project-setup.md`)

**Severity: Major — A2A streaming won't work without it**

The "Install SDK Dependencies" section only lists `@kagenti/adk` and `@a2a-js/sdk`. The A2A streaming client requires `eventsource-parser` to parse Server-Sent Events from the JSON-RPC streaming endpoint.

**Fix:** Add `eventsource-parser` to the required packages table. If `@a2a-js/sdk` is not used for the A2A client (per finding #1), consider whether it should still be listed as a required dependency.

---

## 3. Wrong message structure (`references/messaging.md`)

**Severity: Major — messages will be rejected by the agent**

The doc says user messages require:

| Field | Doc value | Actual value |
|-------|-----------|--------------|
| `kind` | `'message'` | Not present on outgoing messages |
| `role` | `'user'` | `'ROLE_USER'` (ADK 0.8 protocol) |
| Part structure | `{ kind: 'text', text: string }` | `{ text: string }` (no `kind` on parts) |

**Fix:** Update the message structure table. Note that the `role` value is protocol-version-dependent (`'ROLE_USER'` in ADK 0.8+).

---

## 4. Wrong stream event names (`references/messaging.md`)

**Severity: Medium — causes missed events**

The doc says the stream yields events of three "kinds": `status-update`, `message`, `artifact-update`. The actual `StreamResponse` schema uses camelCase object keys:

| Doc says | Actual `StreamResponse` property |
|----------|----------------------------------|
| `status-update` | `statusUpdate` |
| `message` | `message` |
| `artifact-update` | `artifactUpdate` |

These are discriminated by which property is present on the object, not by a `kind` field.

**Fix:** Show the actual `StreamResponse` union shape from `streamResponseSchema`.

---

## 5. LLM proxy `api_base` is a literal, not a template (`references/a2a-client.md`)

**Severity: Medium — breaks LLM fulfillment**

The doc shows:
```typescript
api_base: '{platform_url}/api/v1/openai/',
```

This looks like a template string with `{platform_url}` as a variable to substitute. It is actually a **literal string** — the platform resolves the `{platform_url}` placeholder at runtime. The first implementation incorrectly substituted it with `${ADK_BASE_URL}/api/v1/openai/`.

**Fix:** Add an explicit warning: "The `api_base` value is a **literal string** — do not replace `{platform_url}` with the actual base URL. The ADK platform resolves this placeholder at runtime."

---

## 6. Auth: `react-oidc-context` not recommended strongly enough (`references/authentication.md`)

**Severity: Medium — leads to fragile hand-rolled OIDC**

The doc lists `react-oidc-context` as one option among several for React SPAs and then describes a manual Authorization Code + PKCE flow. This led to a hand-rolled implementation that:
- Manually fetched `/.well-known/openid-configuration`
- Manually generated PKCE code verifier/challenge
- Manually exchanged codes at the token endpoint
- Manually implemented token refresh with timers

The reference implementation uses `react-oidc-context` which handles all of this automatically — including token refresh (`automaticSilentRenew`), OIDC discovery, and autologin via `auth.signinResourceOwnerCredentials()`.

**Fix:** For React projects, strongly recommend `react-oidc-context` as the primary approach. Show the `AuthGate` pattern with `AuthProvider` + `useAuth()`. The manual PKCE flow should be a fallback for non-React projects only. Add `react-oidc-context` to required dependencies for React projects.

---

## 7. Missing: `@kagenti/adk` ships source-only (`references/project-setup.md`)

**Severity: Medium — `tsc -b` build fails without workaround**

The `@kagenti/adk` npm package contains only `src/` with TypeScript source files — no `dist/` with compiled JS/DTS. Vite handles this at dev time via its TypeScript pipeline, but `tsc -b` (used in the default Vite build script) needs type declarations.

Two workarounds are needed:
1. A post-install tsup build step: `cd node_modules/@kagenti/adk && npx tsup src/index.ts src/api.ts src/core.ts src/extensions.ts --format esm,cjs --outDir dist --no-dts`
2. A `paths` mapping in `tsconfig.app.json` to resolve types from source:
   ```json
   "paths": {
     "@kagenti/adk": ["./node_modules/@kagenti/adk/src/index.ts"],
     "@kagenti/adk/core": ["./node_modules/@kagenti/adk/src/core.ts"],
     "@kagenti/adk/extensions": ["./node_modules/@kagenti/adk/src/extensions.ts"],
     "@kagenti/adk/api": ["./node_modules/@kagenti/adk/src/api.ts"]
   }
   ```
   Also requires `"erasableSyntaxOnly": false` since the SDK source uses `enum` declarations.

**Fix:** Add a section about the source-only distribution and the required build/config steps.

---

## 8. Wrong permission format (`references/platform-api.md`)

**Severity: Medium — causes TypeScript errors**

The doc doesn't show the exact `createContextToken` permission format. The first implementation used nested arrays like `[['read', 'write']]` which doesn't match the Zod schema. The correct format uses flat strings:

```typescript
// Correct
grant_global_permissions: {
  a2a_proxy: [providerId],
  llm: ["*"],
},
grant_context_permissions: {
  context_data: ["*"],
},
```

**Fix:** Show a complete `createContextToken` call with exact permission types in `references/platform-api.md`.

---

## 9. Missing `.env` file guidance

**Severity: Low — causes 401 on first run**

The skill creates `.env.example` but never creates a `.env` file. With `VITE_LOCAL_DEV_AUTO_LOGIN=true`, the OIDC client secret is required but defaults to `""` which Keycloak rejects with 401. The first-run experience is a silent auth failure.

**Fix:** Remind the user to copy `.env.example` to `.env` and fill in values. Consider creating a starter `.env` with the Keycloak defaults (`adk-ui-secret`).

---

## 10. Model selection is a mandatory UX step, not a silent auto-pick (`references/a2a-client.md`)

**Severity: Major — agent fails at runtime without model fulfillment**

The doc says to call `matchModelProviders` and "present a model selector", but the phrasing is easy to interpret as optional. The first implementation silently auto-selected the first match without showing any UI. The agent then fails because the LLM fulfillment resolves to an incorrect or unavailable model.

The reference implementation has a dedicated `ModelSelector` component shown as a mandatory step between agent selection and session connect:

1. Fetch agent card to discover demands
2. Call `matchModelProviders` per demand key (each demand may have different suggested models)
3. Show radio buttons per demand key, pre-select first match
4. User confirms selection, then session init receives `selectedModels: Record<string, string>`
5. If agent has no LLM demands, skip the step (pass `{}`)

**Fix:** Add explicit guidance that model selection is a **required UI step**, not an implementation detail. Show the complete flow: agent picker → model selector → connect. The `initSession` function must accept user-selected models as a parameter.

---

## 11. API response shapes not documented (`references/platform-api.md`)

**Severity: Medium — causes runtime errors on first integration**

The doc doesn't show the actual response wrapper shapes. The first implementation assumed `listProviders()` returns an array and `matchModelProviders()` returns a flat list. The actual shapes are:

| Method | Return shape |
|--------|-------------|
| `listProviders({ query: {} })` | `{ items: Provider[] }` — must access `.items` |
| `matchModelProviders()` | `{ items: [{ model_id: string, ... }] }` — must access `.items[].model_id` |

Also, `listProviders` requires `{ query: {} }` as its argument, not `{}`.

**Fix:** Add a "Response Shapes" section to `references/platform-api.md` showing the wrapper objects for key endpoints. Show that `listProviders` takes `{ query: {} }`.

---

## 12. Platform API context token not sent in message metadata (`references/a2a-client.md`)

**Severity: Major — agents cannot call back to the platform API**

The docs mention `getContextToken` in the agent-requirements reference but the a2a-client reference and session setup instructions never show it being included in fulfillments. The first implementation omitted it entirely.

Agents that declare a `PlatformApiExtension` dependency need the context token in every message's metadata under the `https://a2a-extensions.adk.kagenti.dev/services/platform_api/v1` extension URI. Without it, agents that call `File.create()`, read context data, or access any platform resource will fail with an auth error.

The fix is one line during fulfillment setup:

```typescript
fulfillments.getContextToken = () => contextToken;
```

Note: `getContextToken` is marked deprecated in the SDK (the preferred path is sending the token via A2A client headers), but the metadata-based approach is still needed for agents that read it from `PlatformApiExtensionServer`.

**Fix:** In `references/a2a-client.md`, add `getContextToken` to the fulfillments section as a **required** step, not optional. Show it alongside the LLM fulfillment example so it doesn't get skipped.

---

## 13. Extension metadata extraction via `extractUiExtensionData` throws on unexpected shapes (`references/ui-extensions.md`)

**Severity: Medium — crashes the UI when processing agent responses**

The doc recommends using `extractUiExtensionData(trajectoryExtension)(message.metadata)` to extract UI extension data. This runs Zod validation internally, which **throws** when the metadata shape doesn't exactly match the schema — e.g., when trajectory data is a raw array instead of `{ entries: [...] }`.

In practice, the trajectory metadata under `https://a2a-extensions.adk.kagenti.dev/ui/trajectory/v1` arrives as a plain array of entries, not wrapped in an object. The Zod schema expects an object, causing:

```
ZodError: Invalid input: expected object, received array
```

This crash prevents the entire message from rendering, not just the trajectory.

**What works:** Read the metadata directly by extension URI key and handle both shapes:

```typescript
const TRAJECTORY_URI = trajectoryExtension.getUri();

function extractTrajectory(metadata: Record<string, unknown> | undefined) {
  if (!metadata) return undefined;
  const raw = metadata[TRAJECTORY_URI];
  if (!raw) return undefined;
  if (Array.isArray(raw)) return raw;           // raw array
  return (raw as { entries?: unknown[] }).entries; // wrapped object
}
```

**Fix:** In `references/ui-extensions.md`, warn that `extractUiExtensionData` may throw on valid agent metadata. Show the defensive direct-read pattern as the recommended approach. Apply the same pattern for citations and errors.

---

## 14. Streaming text lives in temporary state, not in message list (`references/messaging.md`)

**Severity: Major — agent response vanishes after stream ends**

The doc describes streaming text arriving via `status-update` events and the final response via a `message` event. This leads to an implementation where streaming text is shown in temporary React state and the final message is appended on `message` event.

The problem: many agents send their **entire response** via `statusUpdate` events and never emit a separate `message` event. When the stream ends, the temporary state is cleared and the response vanishes.

**What works (reference pattern):**
1. Add a placeholder agent message to the message list before streaming starts (with `isStreaming: true`)
2. Update that placeholder in-place as `statusUpdate` events arrive (`updateLastMessage`)
3. If a `message` event arrives, replace the placeholder content
4. On stream end, mark `isStreaming: false`

This way the accumulated text always lives in the message list, never in ephemeral state.

**Fix:** In `references/messaging.md`, document the placeholder + update-in-place pattern as the required approach. Explicitly warn that a standalone `message` event is NOT guaranteed.

---

## 15. `SKILL.md` constraint C3 references wrong helpers

**Severity: Low — misleading guidance**

C3 lists `buildMessageBuilder` as a required SDK helper, but the reference implementation constructs messages directly (it's simpler and clearer). `buildMessageBuilder` is a higher-level abstraction that re-invokes `handleAgentCard` on every message — unnecessary when you already have resolved metadata.

**Fix:** Remove `buildMessageBuilder` from C3's mandatory list. Keep `handleAgentCard`, `resolveUserMetadata`, `handleTaskStatusUpdate`, `extractTextFromMessage` as the core helpers.
