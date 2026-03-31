# Project Setup

Reference for Step 1 of the kagenti-adk-ui skill.

## Official Documentation

Read [Getting Started](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/getting-started.mdx) before proceeding.

## Detect Existing Project

Before creating anything, check if the target directory already has a project:

1. Look for `package.json`, `tsconfig.json`, framework config files (e.g., `vite.config.ts`, `next.config.js`).
2. If a project exists, add dependencies to it. Do not create a new project alongside an existing one.
3. If no project exists, scaffold a new one based on the user's framework preference from Entry Questions.

## Install SDK Dependencies

Add the required SDK packages to the project's existing package manager:

```bash
npm install @kagenti/adk @a2a-js/sdk
```

### Package Roles

| Package | Purpose |
| --- | --- |
| `@kagenti/adk` | Platform API client, agent card handling, extension helpers, message utilities, authenticated fetch |
| `@a2a-js/sdk` | A2A protocol client for direct agent communication (message streaming, task management) |

### SDK Entry Points

The `@kagenti/adk` package exposes multiple entry points:

| Import Path | Contents |
| --- | --- |
| `@kagenti/adk` | Core client SDK: `buildApiClient`, `handleAgentCard`, `createAuthenticatedFetch`, `unwrapResult`, `extractTextFromMessage`, `buildMessageBuilder`, `handleTaskStatusUpdate`, `resolveUserMetadata`, `buildLLMExtensionFulfillmentResolver`, `getAgentCardPath` |
| `@kagenti/adk/api` | Platform API client and types |
| `@kagenti/adk/core` | Core utilities, extension types, helpers |
| `@kagenti/adk/extensions` | All A2A extension definitions (service and UI) with their types, schemas, and URIs |

The `@a2a-js/sdk` package:

| Import Path | Contents |
| --- | --- |
| `@a2a-js/sdk/client` | `ClientFactory`, `ClientFactoryOptions`, `DefaultAgentCardResolver`, `JsonRpcTransportFactory`, `Client` type |

## Environment Variables

The UI needs at minimum two environment variables for the ADK base URL and agent provider ID. The naming convention depends on the framework (e.g., `VITE_` prefix for Vite, `NEXT_PUBLIC_` for Next.js).

Create a `.env.example` file with placeholder values so other developers know what to configure.

See the reference example at [`.env.example`](https://github.com/kagenti/adk/blob/main/apps/adk-ts/examples/chat-ui/.env.example) and [`constants.ts`](https://github.com/kagenti/adk/blob/main/apps/adk-ts/examples/chat-ui/src/constants.ts) for the pattern.

## TypeScript Configuration

Ensure `tsconfig.json` has strict mode enabled. The SDK relies on proper type narrowing.

## Project Structure

Follow the file organization pattern in the [chat-ui reference example](https://github.com/kagenti/adk/tree/main/apps/adk-ts/examples/chat-ui/src). Key files to create:

- A constants file for environment variables
- An API module for platform API client and context helpers
- A client module for A2A client setup and session management
- A utilities module for message extraction and metadata resolution
- Type definitions for local types (session, messages)
- Main application entry point and UI component(s)

## Anti-Patterns

- Never install `@kagenti/adk` and separately install `a2a-sdk` as a Python package. The JS SDK is `@a2a-js/sdk`.
- Never create both `package.json` and a separate dependency manifest. Use the existing one.
- Never skip TypeScript strict mode. The SDK relies on proper type narrowing.
