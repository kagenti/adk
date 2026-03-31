---
name: kagenti-adk-ui
description: Creates custom TypeScript UIs for Kagenti ADK agents using the @kagenti/adk SDK and A2A protocol. Use when building a custom frontend, chat interface, or interactive UI for an existing Kagenti ADK agent; not for wrapping Python agents or building agents themselves.
---

# Kagenti ADK UI

Guide for building custom TypeScript UIs for [Kagenti ADK](https://github.com/kagenti/adk/blob/main/docs/stable/introduction/welcome.mdx) agents using the `@kagenti/adk` SDK.

## Table of Contents

- [Security Requirements](#security-requirements)
- [Constraints (must follow)](#constraints-must-follow)
- [Integration Workflow Checklist](#integration-workflow-checklist)
- [Entry Questions](#entry-questions)
- [Readiness Check](#readiness-check)
- [Step 1 – Project Setup](#step-1--project-setup)
- [Step 2 – Authentication](#step-2--authentication)
- [Step 3 – Platform API Client](#step-3--platform-api-client)
- [Step 4 – A2A Client & Agent Requirements](#step-4--a2a-client--agent-requirements)
- [Step 5 – Messaging & Streaming](#step-5--messaging--streaming)
- [Step 6 – Agent Responses](#step-6--agent-responses)
- [Step 7 – Interactive Features](#step-7--interactive-features)
- [Step 8 – UI Extensions](#step-8--ui-extensions)
- [Step 9 – Error Handling](#step-9--error-handling)
- [Step 10 – Styling & Polish](#step-10--styling--polish)
- [Step 11 – Update README](#step-11--update-readme)
- [Anti-Patterns](#anti-patterns)
- [Failure Conditions](#failure-conditions)
- [Finalization Report (Required)](#finalization-report-required)
- [Verification Checklist](#verification-checklist)

## Security Requirements

- Never expose API keys, tokens, or secrets in client-side code or bundle output.
- Use server-side token creation for context tokens; never create tokens with elevated permissions client-side.
- Never log, print, or persist secret values in browser console, local storage, or DOM.
- Validate and sanitize all agent response content before rendering (especially HTML/markdown).
- Use `createAuthenticatedFetch` for all authenticated requests; never manually append tokens to URLs.
- Context tokens must request the minimum permissions required (`grant_global_permissions`, `grant_context_permissions`).

## Constraints (must follow)

| ID  | Rule |
| --- | ---- |
| C1  | **No agent-side changes.** Only create or modify client/UI code. Do not modify the agent's Python code, server wrapper, or backend configuration. |
| C2  | **Strict minimal scope.** Do not add authentication systems, backend servers, databases, or deployment infrastructure unless explicitly requested. Build the simplest working UI first. |
| C3  | **SDK-first implementation.** Use `@kagenti/adk` SDK helpers (`handleAgentCard`, `resolveUserMetadata`, `buildMessageBuilder`, `handleTaskStatusUpdate`, `extractTextFromMessage`, `buildLLMExtensionFulfillmentResolver`) instead of manually constructing protocol objects. Do not reimplement what the SDK provides. |
| C4  | **Documentation-first for SDK usage.** Before implementing any SDK feature, read the corresponding documentation URL (listed in each step). Extract exact imports, function signatures, and types from the docs. Do not guess APIs or rely on outdated memory. |
| C5  | **Package-first for imports.** If documentation is unclear on exact import paths, inspect the installed `@kagenti/adk` package to discover correct exports. The installed package is authoritative for import paths; documentation is authoritative for behavior and patterns. |
| C6  | **Type safety required.** Use TypeScript with strict mode. Use SDK-provided types (`Message`, `AgentCard`, `TaskStatusUpdateEvent`, `Part`, `Artifact`, etc.) for all protocol objects. Never use `any` for SDK types. |
| C7  | **Detect existing tooling.** If the project already uses a specific framework (React, Next.js, Vue, vanilla), build within that framework. If the project uses an existing package manager or bundler, use it. Never force a framework change or create duplicate configuration. |
| C8  | **Permissions principle of least privilege.** Context tokens must only request permissions the UI actually needs. Do not grant `['*']` for permissions that can be scoped to specific providers or resources. |
| C9  | **No hardcoded agent identifiers.** Provider IDs, base URLs, and model names must come from environment variables or configuration, never hardcoded in source. |
| C10 | **Handle all task status update types.** The UI must handle or gracefully degrade for every `TaskStatusUpdateType` the agent may emit: `FormRequired`, `SecretRequired`, `OAuthRequired`, `ApprovalRequired`, `TextInputRequired`. |
| C11 | **Context & Memory Optimization.** Do not attempt the entire UI in one pass. Follow the checklist iteratively. Use the built-in task/todo tracking tool to track progress — do not create separate markdown tracking files. Do not paste massive error logs; extract only the relevant error. |
| C12 | **Preserve agent contract.** The UI must faithfully represent the agent's capabilities, forms, and extension demands. Do not skip required form fields, ignore agent demands, or fabricate metadata the agent did not request. |
| C13 | **Read SDK documentation first.** Before starting any implementation, read the official guide: [Custom UI Getting Started](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/getting-started.mdx). |

---

## Context & Memory Optimization

To ensure the highest success rate and prevent context window exhaustion:

1. **Iterative Progress**: Execute the [Integration Workflow Checklist](#integration-workflow-checklist) strictly step-by-step. Use the built-in task/todo tracking tool to mirror the checklist items and mark them off as you complete each step.
2. **Minimize Terminal Output**: When debugging, extract specifically the error message and immediate stack frame, omitting framework internals.
3. **Targeted Code Reading**: Do not repeatedly load large SDK source files or documentation if they haven't changed.
4. **Do NOT create tracking files**: Do not create `task.md`, `implementation_plan.md`, or similar markdown artifacts for progress tracking.

## Source-of-Truth Precedence (Required)

For every UI task, use this exact precedence order:

1. **Absolute Primary (highest priority):** Installed `@kagenti/adk` package exports for all import paths, function signatures, and types. Run `npx tsc --noEmit` to validate.
2. **Primary (required second):** Local skill-provided files in the `references/` folder for architectural patterns, SDK usage patterns, and implementation guidance.
3. **Secondary:** Official documentation URLs linked by this skill for detailed API behavior and examples.
4. **Tertiary:** The [chat-ui reference example](https://github.com/kagenti/adk/tree/main/apps/adk-ts/examples/chat-ui) for practical patterns.
5. **Final step:** Runtime verification (build succeeds, UI renders, agent communication works) after implementation is complete.

If you use step 3 or 4, explicitly record what was missing from the skill references and why fallback was necessary.

**CRITICAL WORKFLOW REQUIREMENT:** For _every_ SDK feature you implement, follow these exact steps in order:

1. Decide which SDK feature is needed.
2. **READ the documentation URL provided in the step below.** This is mandatory and happens before any code edits.
3. Extract the correct imports, function names, parameter types, and return types directly from the documentation.
4. **Only AFTER reading the documentation**, proceed to write code. Never guess imports or rely on outdated memory.
5. If docs are incomplete, inspect the installed package as fallback and note the specific gap.

---

## Integration Workflow Checklist

Copy this checklist into your context and check off items as you complete them:

```
Task Progress:
- [ ] Entry Questions
- [ ] Readiness Check
- [ ] Step 1: Project Setup (requires reading docs)
- [ ] Step 2: Authentication (requires reading docs)
- [ ] Step 3: Platform API Client (requires reading docs)
- [ ] Step 4: A2A Client & Agent Requirements (requires reading docs)
- [ ] Step 5: Messaging & Streaming (requires reading docs)
- [ ] Step 6: Agent Responses (requires reading docs)
- [ ] Step 7: Interactive Features (requires reading docs for each feature)
- [ ] Step 8: UI Extensions (requires reading docs for each extension)
- [ ] Step 9: Error Handling (requires reading docs)
- [ ] Step 10: Styling & Polish
- [ ] Step 11: Update README
- [ ] (Optional) Agent-Specific Study — only if user is targeting a specific agent
- [ ] Finalization Report (required)
- [ ] Verification Checklist (required)
```

**STOP GATE:** After Step 11, you MUST complete the Finalization Report and walk through every item in the Verification Checklist before reporting completion. The task is NOT done until both are finished.

## Entry Questions

Infer answers from the user's prompt where possible, then present all three answers to the user for explicit confirmation. Do not proceed to Readiness Check until the user confirms.

1. **Framework preference**: Are you adding a UI to an existing project, or starting fresh? If fresh, do you have a framework preference (React, Next.js, Vue, vanilla)? Default: React + Vite.
2. **Agent-specific targeting**: Are you building this UI for a specific agent, or a general-purpose UI that works with any ADK agent?
   - If **specific agent**: After the core UI is built, we will do an optional Agent-Specific Study step to add tailored features for that agent (e.g., custom form rendering, special artifact handling).
   - If **general-purpose**: The SDK's `handleAgentCard()`, `handleTaskStatusUpdate()`, and extension system handle all agents dynamically at runtime. No agent-specific study is needed.
3. **Authentication**: Is the ADK platform running with authentication enabled or disabled? **Default is enabled** (Keycloak as the OIDC provider). If enabled, the UI must implement an OIDC login flow (redirect to the provider, handle callback, obtain tokens) before making API calls. For local development, the platform also supports an **autologin mode** (`LOCAL_DEV_AUTO_LOGIN=true`) that presents a username/password form instead of redirecting to the OIDC provider — ask if they want to support this. If auth is disabled (`AUTH__DISABLE_AUTH=true` on the server, `OIDC_ENABLED=false` on the UI), skip the authentication step entirely.
4. **Feature scope**: Any specific features beyond the standard chat interface? (e.g., settings panel, artifact viewer, file uploads). Note: trajectory display is always included by default.

## Readiness Check

Run each check, report the results to the user, and only proceed if all pass.

- [ ] Node.js >= 18 is installed and available.
- [ ] A package manager is available (`npm`, `pnpm`, or `yarn`).
- [ ] The ADK platform API base URL is known (or will be `http://adk-api.localtest.me:8080` for local dev).
- [ ] A provider ID is known or will be discovered at runtime.
- [ ] Authentication status is known (default: enabled). If enabled, the OIDC issuer URL and client ID are available.

If any item fails, stop and resolve it with the user before continuing.

**STOP GATE:** Do not proceed to Step 1 until Entry Questions are confirmed by the user and all Readiness Check items pass.

## Step 1 – Project Setup

**Read [references/project-setup.md](references/project-setup.md) and follow it completely for Step 1.**

---

## Step 2 – Authentication

The ADK platform uses OIDC authentication by default (Keycloak). The UI must obtain a user access token before making any platform API calls.

**Read [references/authentication.md](references/authentication.md) and follow it completely for Step 2.**

---

## Step 3 – Platform API Client

**Read [references/platform-api.md](references/platform-api.md) and follow it completely for Step 3.**

---

## Step 4 – A2A Client & Agent Requirements

**Read [references/a2a-client.md](references/a2a-client.md) and follow it completely for Step 4.**

---

## Step 5 – Messaging & Streaming

**Read [references/messaging.md](references/messaging.md) and follow it completely for Step 5.**

---

## Step 6 – Agent Responses

**Read [references/agent-responses.md](references/agent-responses.md) and follow it completely for Step 6.**

---

## Step 7 – Interactive Features

Agents may use forms, approvals, canvas, OAuth, or secrets requests. The UI must handle all `TaskStatusUpdateType` variants dynamically.

**Read [references/interactive-features.md](references/interactive-features.md) for detection, rendering, and submission patterns for each interactive feature.**

---

## Step 8 – UI Extensions

Trajectory display is **required** in every implementation. Additionally, enhance the UI with other agent-emitted metadata: citations, streaming patches, settings, and error details.

**Read [references/ui-extensions.md](references/ui-extensions.md) for extension selection and implementation.**

---

## Step 9 – Error Handling

Handle both platform API errors and agent task failures gracefully.

### Platform API Errors

Use `unwrapResult()` for all API calls. Catch `ApiErrorException` and inspect `error.type`:

| Error Type | Meaning | UI Response |
| --- | --- | --- |
| `http` | Server returned error status | Show error message, offer retry |
| `network` | Connection failed | Show connection error, offer retry |
| `parse` | Response body unparseable | Show generic error, log for debugging |
| `validation` | Response didn't match schema | Show generic error, log for debugging |

### Agent Task Failures

The agent may emit errors via the Error UI extension. Extract error metadata from message metadata using `extractUiExtensionData(errorExtension)` and display the error message, stack trace (if included), and context data.

### Required Error States

The UI must display clear feedback for:

- [ ] Connection failures (platform unreachable)
- [ ] Session initialization failures (context/token creation)
- [ ] Agent communication failures (A2A client errors)
- [ ] Agent-reported errors (Error extension metadata)
- [ ] Timeout / cancellation states

See the [official error handling guide](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/error-handling.mdx) for detailed patterns.

---

## Step 10 – Styling & Polish

Apply styling appropriate to the project's existing design system. If no design system exists:

1. Use clean, minimal CSS (or CSS modules / Tailwind if already in the project).
2. Ensure responsive layout for the chat/interaction area.
3. Distinguish user messages from agent messages visually.
4. Show loading/thinking states during agent processing.
5. Show connection status (connecting, ready, error).

Do not add a CSS framework unless explicitly requested.

---

## Step 11 – Update README

Update the project's `README.md` (or create one if missing) with:

1. **Install dependencies** using the project's package manager.
2. **Environment Configuration** — document required environment variables (`VITE_ADK_BASE_URL`, `VITE_ADK_PROVIDER_ID`, or equivalent).
3. **Run the development server** with the appropriate command (e.g., `npm run dev`).
4. **Agent requirements** — note which agent must be running and at what address.
5. **Build for production** — include the build command if applicable.

---

## (Optional) Agent-Specific Study

**Only perform this step if the user answered "specific agent" in the Entry Questions.**

If building additional features tailored to a particular agent, study that agent's card and capabilities:

1. **Get the agent card**: Fetch `<BASE_URL>/<PROVIDER_PATH>/.well-known/agent-card.json` or use `client.getAgentCard()`.
2. **Identify specific demands**: List service extension demands (LLM, embedding, secrets, forms, OAuth, MCP) this agent declares.
3. **Identify specific UI extensions**: List UI extensions this agent emits (trajectory, citations, canvas, approval, error, streaming).
4. **Classify interaction mode**: Determine `single-turn` or `multi-turn` from the agent detail extension.
5. **Map custom inputs/outputs**: Identify agent-specific forms, file types, or artifact formats that would benefit from tailored rendering.

Use this analysis to add agent-specific enhancements on top of the universal UI — for example, a custom form layout for the agent's initial form, specialized artifact rendering, or a dedicated trajectory visualization.

> [!NOTE]
> The base UI built in Steps 1–11 already handles any ADK agent dynamically via the SDK's extension system. This step only adds polish for a known agent.

---

## Anti-Patterns

- **Never access `message.parts[0].text` directly.** Message content is multipart. Always use `extractTextFromMessage(message)` or iterate parts by `kind`.
- **Never construct A2A messages manually.** Use `buildMessageBuilder()` to create properly structured messages with metadata.
- **Never construct metadata manually.** Use `resolveUserMetadata()` for form submissions, approvals, and canvas edits. Use `handleAgentCard()` + `resolveMetadata()` for agent requirement fulfillments.
- **Never skip `handleTaskStatusUpdate()`.** Status updates may require UI interaction (forms, approvals, OAuth). Ignoring them breaks the agent interaction flow.
- **Never assume all messages have text.** Messages can contain file parts, data parts, or be empty status updates. Always check part `kind` before accessing properties.
- **Never hardcode provider IDs or base URLs.** Use environment variables or configuration.
- **Never create context tokens client-side in production.** Token creation should happen server-side; the example pattern is for development only.
- **Never ignore the `final` flag on status updates.** Only the final message represents the complete agent response. Intermediate messages may be partial.
- **Never treat `adk://` file URIs as HTTP URLs.** File URIs from artifacts must be resolved through the platform API, not fetched directly.
- **Never store tokens in localStorage or cookies without explicit user approval.** Prefer in-memory session state.
- **Never render agent HTML output without sanitization.** Agent text may contain user-influenced content.
- **Never skip form field validation.** Validate required fields and types before submitting form responses to the agent.
- **Never use `llm_config.identifier` as the model name.** Use `llm_config.api_model` when displaying or resolving LLM configuration.
- **Never ignore streaming events.** Process `status-update`, `message`, and `artifact-update` event kinds from the message stream. Missing events causes incomplete UI state.

## Failure Conditions

- If the agent card cannot be fetched, stop and report that the agent is unreachable.
- If required SDK documentation cannot be read, stop and report that execution cannot continue without current docs.
- If the agent demands extensions the UI does not implement, stop and report the gap explicitly with the extension URI.
- If `npx tsc --noEmit` fails with import errors after implementation, fix the imports before proceeding.

---

## Finalization Report (Required)

Before completion, provide all of the following:

1. **Agent integration summary:** Which agent demands are fulfilled, which UI extensions are rendered, and the interaction mode (single-turn / multi-turn).
2. **Feature coverage:** List each interactive feature implemented (forms, approvals, canvas, OAuth, secrets, trajectory, citations, streaming, error display).
3. **Unimplemented features:** List any agent demands or extensions that were intentionally skipped, with justification.
4. **Environment variables:** List all required environment variables and their purpose.
5. **Testing prompt:** Ask the user if they want to test the UI. If yes, ensure the agent is running, start the dev server, and verify:
   - The UI loads without console errors.
   - A message can be sent and a response is received.
   - Any forms or interactive features work correctly.
6. **Build prompt:** Ask the user if they want to verify the production build succeeds (`npm run build` or equivalent).

---

## Verification Checklist (Required)

After building the UI, confirm:

### Code Quality

- [ ] `npx tsc --noEmit` passes with no errors
- [ ] Every import resolves to a real, installed module
- [ ] No `any` types used for SDK objects
- [ ] No hardcoded provider IDs, base URLs, or API keys in source
- [ ] Environment variables documented and used for all configuration

### SDK Usage

- [ ] `buildApiClient()` used for platform API access
- [ ] `createAuthenticatedFetch()` used for all authenticated requests
- [ ] `handleAgentCard()` + `resolveMetadata()` used for agent requirement resolution
- [ ] `buildMessageBuilder()` or proper message structure used for sending messages
- [ ] `handleTaskStatusUpdate()` used for processing status updates
- [ ] `extractTextFromMessage()` or part-by-kind iteration used for reading responses
- [ ] `resolveUserMetadata()` used for form/approval/canvas submissions
- [ ] `unwrapResult()` used for API error handling

### Authentication (if auth enabled — default)

- [ ] OIDC login flow implemented (redirect to provider, handle callback, exchange code for token)
- [ ] User access token stored in memory (not localStorage/cookies)
- [ ] Token refresh implemented before expiration
- [ ] Logout clears tokens and revokes session at OIDC provider
- [ ] `createAuthenticatedFetch(userAccessToken)` used for all platform API calls
- [ ] (If local dev autologin) Credentials provider implemented as alternative to OIDC redirect

### Agent Communication

- [ ] Context created via platform API (with authenticated fetch)
- [ ] Context token created with minimal required permissions
- [ ] A2A client created with authenticated fetch (using context token)
- [ ] Agent card fetched and demands resolved
- [ ] Message streaming implemented (not just request-response)
- [ ] All `TaskStatusUpdateType` variants handled or gracefully degraded

### Interactive Features (if applicable)

- [ ] Forms rendered from `FormRequired` status updates
- [ ] Form submissions sent via `resolveUserMetadata({ form: values })`
- [ ] Approval requests rendered and responses submitted
- [ ] OAuth redirects handled if agent demands OAuth
- [ ] Secret requests shown to user if agent demands secrets

### Error Handling

- [ ] API errors caught and displayed
- [ ] Agent errors extracted from Error extension metadata
- [ ] Connection failures shown with retry option
- [ ] Loading/thinking states shown during agent processing

### Validation (must be performed live)

- [ ] Dev server starts without errors
- [ ] UI loads in browser without console errors
- [ ] Send a test message and receive agent response
- [ ] Verify any forms or interactive features render and submit correctly
- [ ] Production build succeeds (`npm run build` or equivalent)
