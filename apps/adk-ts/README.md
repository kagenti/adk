# Kagenti ADK Client SDK

TypeScript/JavaScript client SDK for building applications that interact with Kagenti ADK agents.

[![npm version](https://img.shields.io/npm/v/%40kagenti%2Fadk.svg?style=plastic)](https://www.npmjs.com/package/@kagenti/adk)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=plastic)](https://opensource.org/licenses/Apache-2.0)
[![LF AI & Data](https://img.shields.io/badge/LF%20AI%20%26%20Data-0072C6?style=plastic&logo=linuxfoundation&logoColor=white)](https://lfaidata.foundation/projects/)

## Overview

The `@kagenti/adk` provides TypeScript and JavaScript tools for building client applications that communicate with
agents deployed on Kagenti ADK. It includes utilities for handling the A2A (Agent2Agent) protocol, working with
extensions, and calling the Kagenti ADK platform API.

## Key Features

- **A2A Protocol Support** - Parse agent cards and task status updates with typed utilities
- **Extension System** - Resolve service demands and UI metadata with typed helpers
- **Platform API Client** - Typed access to core platform resources
- **Type Safe Responses** - Zod validated payloads with structured API error helpers

## Installation

```bash
npm install @kagenti/adk
```

## Quickstart

```typescript
import {
  buildApiClient,
  buildAgentClient,
  createAuthenticatedFetch,
  unwrapResult,
  handleAgentCard,
  handleTaskStatusUpdate,
  resolveUserMetadata,
  TaskStatusUpdateType,
  type Fulfillments,
} from '@kagenti/adk';

const baseUrl = 'https://your-adk-instance.com'; // or http://adk-api.localtest.me:8080 for local development
const accessToken = '<user-access-token>';

const api = buildApiClient({
  baseUrl,
  fetch: createAuthenticatedFetch(accessToken),
});

const providers = unwrapResult(await api.listProviders());
const providerId = providers[0]?.id;

const context = unwrapResult(await api.createContext({ provider_id: providerId }));
const contextToken = unwrapResult(
  await api.createContextToken({
    context_id: context.id,
    grant_global_permissions: {
      llm: ['*'],
      embeddings: ['*'],
      a2a_proxy: ['*'],
      providers: ['read'],
    },
    grant_context_permissions: {
      files: ['*'],
      vector_stores: ['*'],
      context_data: ['*'],
    },
  }),
);

const client = await buildAgentClient({
  baseUrl,
  providerId,
  token: contextToken.token,
});

const card = await client.getAgentCard();
const { resolveMetadata, demands } = handleAgentCard(card);

const selectedLlmModels: Record<string, string> = { default: 'gpt-4o' };

const fulfillments: Fulfillments = {
  llm: demands.llmDemands
    ? async ({ llm_demands }) => ({
        llm_fulfillments: Object.fromEntries(
          Object.keys(llm_demands).map((key) => [
            key,
            {
              identifier: 'llm_proxy',
              api_base: '{platform_url}/api/v1/openai/',
              api_key: contextToken.token,
              api_model: selectedLlmModels[key],
            },
          ]),
        ),
      })
    : undefined,
};

const agentMetadata = await resolveMetadata(fulfillments);

const stream = client.sendMessageStream({
  message: {
    messageId: crypto.randomUUID(),
    role: 'ROLE_USER',
    contextId: context.id,
    parts: [{ text: 'Hello' }],
    metadata: agentMetadata,
  },
});

let taskId: string | undefined;

for await (const event of stream) {
  if ('task' in event && event.task) {
    taskId = event.task.id;
  }

  if ('statusUpdate' in event && event.statusUpdate) {
    taskId = event.statusUpdate.taskId;

    for (const update of handleTaskStatusUpdate(event.statusUpdate)) {
      switch (update.type) {
        case TaskStatusUpdateType.FormRequired:
        // Render form
        case TaskStatusUpdateType.OAuthRequired:
        // Redirect to update.url
        case TaskStatusUpdateType.SecretRequired:
        // Prompt for secrets
        case TaskStatusUpdateType.ApprovalRequired:
        // Request approval
        case TaskStatusUpdateType.TextInputRequired:
        // Prompt for text input
      }
    }
  }

  if ('message' in event && event.message) {
    // Render message parts and metadata
  }

  if ('artifactUpdate' in event && event.artifactUpdate) {
    // Render artifacts
  }
}
```

## Core APIs

- `buildAgentClient` creates a fully configured A2A client with JSON-RPC + SSE transport.
- `buildApiClient` returns a typed API client for platform endpoints.
- `handleAgentCard` extracts extension demands and returns `resolveMetadata`.
- `handleTaskStatusUpdate` parses A2A status updates into UI actions.
- `resolveUserMetadata` builds metadata when the user submits forms, canvas edits, or approvals.
- `createAuthenticatedFetch` helps add bearer auth headers to API calls.
- `buildLLMExtensionFulfillmentResolver` matches LLM providers and returns fulfillments.
- `unwrapResult` returns the response data on success, throws an `ApiErrorException` on error

## Extensions

Service extensions (client fulfillments):

- **Embedding** - Provide embedding access (`api_base`, `api_key`, `api_model`) for RAG or search.
- **Form** - Request structured user input via forms.
- **LLM** - Resolve model access and credentials for text generation.
- **MCP** - Connect Model Context Protocol services and tools.
- **OAuth** - Provide OAuth credentials or redirect URIs.
- **Platform API** - Inject context token metadata for platform access.
- **Secrets** - Supply or request secret values securely.

UI extensions (message metadata your UI can render):

- **Agent Detail** - Show agent specific metadata and context.
- **Approval** - Ask the user to approve actions or tool calls.
- **Canvas** - Provide canvas edit requests and updates.
- **Citation** - Display inline source references.
- **Error** - Render structured error messages.
- **Form Request** - Render interactive forms in the UI.
- **Settings** - Read or update runtime configuration values.
- **Trajectory** - Render execution traces or reasoning steps.

## Documentation

- [Kagenti ADK Documentation](https://github.com/kagenti/adk/blob/main/docs/stable)
- [Getting Started](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/getting-started.mdx)
- [A2A Client Integration](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/a2a-client.mdx)
- [Agent Requirements](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/agent-requirements.mdx)
- [Platform API Client](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/platform-api-client.mdx)

## Resources

- [GitHub Repository](https://github.com/kagenti/adk)
- [npm Package](https://www.npmjs.com/package/@kagenti/adk)

## Contributing

Contributions are welcome! Please see the
[Contributing Guide](https://github.com/kagenti/adk/blob/main/CONTRIBUTING.md) for details.

## Support

- [GitHub Issues](https://github.com/kagenti/adk/issues)
- [GitHub Discussions](https://github.com/kagenti/adk/discussions)

---

Developed by contributors to the Kagenti project, this initiative is part of the
[Linux Foundation AI & Data program](https://lfaidata.foundation/projects/). Its development follows open,
collaborative, and community-driven practices.
