# Platform API Client

Reference for Step 3 of the kagenti-adk-ui skill.

## Official Documentation

Read [Platform API Client](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/platform-api-client.mdx) and [Permissions and Tokens](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/permissions-and-tokens.mdx) before proceeding.

## Creating the API Client

Use `buildApiClient({ baseUrl, fetch })` from `@kagenti/adk`. When authentication is enabled (default), pass `createAuthenticatedFetch(userAccessToken)` as the `fetch` parameter, using the user access token obtained in Step 2. When auth is disabled, the `fetch` parameter can be omitted.

See [`api.ts`](https://github.com/kagenti/adk/blob/main/apps/adk-ts/examples/chat-ui/src/api.ts) for the reference implementation.

## Context Creation

Every agent session requires a context. Create one tied to the agent's provider using `api.createContext({ provider_id })`. The returned `Context` object contains an `id` that identifies the session.

## Context Token Creation

Create a token that grants the UI permissions to interact with the agent using `api.createContextToken()`.

### Permission Scoping

| Permission | Scope | Purpose |
| --- | --- | --- |
| `a2a_proxy` | Global | Allows proxying A2A requests to the specified agent provider(s) |
| `llm` | Global | Allows using LLM model providers (`['*']` for any, or specific provider IDs) |
| `context_data` | Context | Allows reading/writing context data (history, files, variables) |

See [`api.ts`](https://github.com/kagenti/adk/blob/main/apps/adk-ts/examples/chat-ui/src/api.ts) for the exact permission structure used in the reference example.

> [!CAUTION]
> In production, token creation must happen server-side. The client should receive a pre-created token, not create one itself. The example pattern is for development only.

### Principle of Least Privilege (C8)

Only request permissions the UI actually needs:

- If the agent does not require LLM fulfillment, omit `llm`.
- If the UI only reads context data, scope `context_data` to `['read']`.
- Always scope `a2a_proxy` to the specific provider ID, never `['*']`.

## Error Handling with `unwrapResult`

Every API call returns `ApiResult<T>`. Always use `unwrapResult()` to extract the data or throw an `ApiErrorException`. The exception's `error.type` field is one of: `'http'`, `'network'`, `'parse'`, `'validation'`.

See the [error handling documentation](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/error-handling.mdx) for detailed patterns.

## Available API Endpoints

The `api` object returned by `buildApiClient` provides methods for:

| Method Group | Key Methods | When Needed |
| --- | --- | --- |
| Contexts | `createContext()`, `createContextToken()`, `readContextHistory()` | Always (session setup) |
| Providers | `listProviders()`, `readProvider()` | Agent discovery |
| Files | `createFile()`, `readFile()`, `readFileContent()` | File upload/download UIs |
| Model Providers | `listModelProviders()`, `matchModelProviders()` | LLM fulfillment resolution |
| Variables | `listVariables()`, `updateVariables()` | Context variable management |
| Configuration | `readSystemConfiguration()` | System-level config |
| User Feedback | `createUserFeedback()` | Feedback collection UIs |

## ContextToken Type

The `createContextToken` response includes a `token` string field. Use `contextToken.token` with `createAuthenticatedFetch()` for all subsequent authenticated requests.

## API Response Shapes

API list methods return wrapper objects, not raw arrays. Always access `.items` on the result:

| Method | Return Shape | Access Pattern |
| --- | --- | --- |
| `listProviders({ query: {} })` | `{ items: Provider[] }` | `result.items` |
| `matchModelProviders(...)` | `{ items: [{ model_id, ... }] }` | `result.items[].model_id` |
| `listModelProviders(...)` | `{ items: ModelProvider[] }` | `result.items` |
| `readContextHistory(...)` | `{ items: HistoryItem[] }` | `result.items` |

> [!IMPORTANT]
> `listProviders` requires `{ query: {} }` as its argument, not `{}` or no argument.

## Anti-Patterns

- Never call `buildApiClient` multiple times with different base URLs in the same session.
- Never pass the full `ContextToken` object where only `token` (the string) is needed.
- Never create context tokens with `['*']` for `a2a_proxy` — always specify the provider ID.
- Never skip `unwrapResult()` — accessing `.data` directly on the result without checking `.ok` will cause runtime errors.
