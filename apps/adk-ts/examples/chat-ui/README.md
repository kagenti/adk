# Chat UI Example

Minimal React + Vite chat interface for Kagenti ADK agents using the `@kagenti/adk` SDK.

## Prerequisites

- Node.js >= 18
- A running Kagenti ADK platform **with authentication disabled**

### Disabling authentication

Authentication is enabled by default. This example does not implement an OIDC login flow, so you must disable auth on the platform.

**Using Helm values:**

```yaml
auth:
  enabled: false
```

**Using the CLI** (add to your Helm overrides):

```bash
kagenti platform start --set auth.enabled=false
```

**Using environment variables** (when running adk-server directly):

```bash
AUTH__DISABLE_AUTH=true
```

For a full custom UI with authentication, see the [Custom UI docs](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/getting-started.mdx).

## Setup

1. Copy the environment file and configure it:

   ```bash
   cp .env.example .env
   ```

2. Set `VITE_ADK_BASE_URL` to your platform API URL and `VITE_ADK_PROVIDER_ID` to the agent provider you want to chat with. You can find provider IDs via the platform API (`GET /api/v1/providers`).

3. Install dependencies and start the dev server:

   ```bash
   pnpm install
   pnpm dev
   ```

4. Open `http://localhost:5173` in your browser.
