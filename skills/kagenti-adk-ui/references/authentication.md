# Authentication

Reference for Step 2 of the kagenti-adk-ui skill.

## Official Documentation

Read [Permissions and Tokens](https://github.com/kagenti/adk/blob/main/docs/stable/custom-ui/permissions-and-tokens.mdx) and the [Deployment Guide (auth section)](https://github.com/kagenti/adk/blob/main/docs/stable/deploy-agent-stack/deployment-guide.mdx) before proceeding.

## Overview

The ADK platform uses OIDC authentication by default (Keycloak is the default provider, but the platform supports any standard OIDC-compliant provider). Before the UI can call any platform API endpoint, it must obtain a **user access token** via the OIDC login flow.

There are two independent token types in the system:

| Token Type | Issued By | Purpose | Lifetime |
| --- | --- | --- | --- |
| **User Access Token** | OIDC provider (Keycloak) | Authenticate the user for all platform API calls | Provider-configured (typically 5–30 min, auto-refreshable) |
| **Context Token** | ADK Server (`/api/v1/contexts/{id}/token`) | Grant agents scoped access to platform resources during a conversation | 20 minutes |

The user access token is needed first (Step 2). The context token is created later using the platform API (Step 3).

## Auth Disabled Mode

If the user confirmed in Entry Questions that auth is disabled (`AUTH__DISABLE_AUTH=true` on the server, `OIDC_ENABLED=false` on the UI), skip this step entirely. The platform API will accept unauthenticated requests. Note: auth is **enabled by default** — disabling it is only recommended for local development.

## OIDC Login Flow (Default)

When auth is enabled (the default), the UI must implement the **OAuth 2.0 Authorization Code Flow**:

1. **Redirect to OIDC provider**: Send the user to the provider's authorization endpoint with the client ID and redirect URI.
2. **User authenticates**: The user enters credentials at the provider's login page.
3. **Callback with authorization code**: The provider redirects back to the UI's callback URL with an authorization code.
4. **Exchange code for tokens**: The UI exchanges the authorization code for an access token (and refresh token) at the provider's token endpoint.
5. **Store token in memory**: Keep the access token in memory for API calls. Never persist to localStorage or cookies without explicit user approval.

## Local Dev Autologin Mode (Optional)

For local development, the platform supports an **autologin mode** that replaces the OIDC redirect with a simple username/password credentials form. This is controlled by the `LOCAL_DEV_AUTO_LOGIN` environment variable.

When `LOCAL_DEV_AUTO_LOGIN=true`:

1. **Show a credentials form** instead of redirecting to the OIDC provider. The form has username and password fields.
2. **Exchange credentials directly**: POST to the OIDC provider's token endpoint using the **Resource Owner Password Credentials Grant** (`grant_type=password`).
3. **Receive tokens**: The response contains `access_token`, `refresh_token`, and `expires_in` — handle them the same as the standard OIDC flow.

This mode uses the same OIDC issuer URL, client ID, and client secret as the standard flow — only the grant type differs.

### Reference implementation

See [`apps/adk-ui/src/app/(auth)/auth.ts`](https://github.com/kagenti/adk/blob/main/apps/adk-ui/src/app/(auth)/auth.ts) — the `createLocalDevCredentialsProvider()` function implements this pattern using NextAuth's Credentials provider. The `assembleProviders()` function selects between autologin and standard OIDC based on the `isLocalDevAutoLogin` flag.

### Implementation pattern

```typescript
// Pseudocode — adapt to your framework
if (LOCAL_DEV_AUTO_LOGIN) {
  // Show username/password form, then:
  const response = await fetch(`${issuerUrl}/protocol/openid-connect/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'password',
      client_id: clientId,
      client_secret: clientSecret,
      username,
      password,
      scope: 'openid email profile',
    }),
  });
  const { access_token, refresh_token, expires_in } = await response.json();
} else {
  // Standard OIDC Authorization Code Flow (redirect to provider)
}
```

> **Note:** The token endpoint path `/protocol/openid-connect/token` is Keycloak-specific. For other OIDC providers, discover the token endpoint from the provider's `/.well-known/openid-configuration` document.

### Required OIDC Configuration

The UI needs these environment variables (names depend on your framework):

| Variable | Example Value | Purpose |
| --- | --- | --- |
| OIDC issuer URL | `http://keycloak.localtest.me:8080/realms/adk` | OIDC discovery endpoint base |
| OIDC client ID | `adk-ui` | Client registered in the OIDC provider for this UI |
| OIDC client secret | (if confidential client) | Only needed for server-side exchanges |
| OIDC redirect URI | `http://localhost:5173/auth/callback` | Where the provider redirects after login |
| LOCAL_DEV_AUTO_LOGIN | `false` | Set to `true` to use credentials form instead of OIDC redirect (local dev only) |

The OIDC discovery document at `{issuer}/.well-known/openid-configuration` provides the exact authorization, token, and logout endpoint URLs. Always prefer discovery over hardcoded endpoint paths.

### Local Development

For local development with the default ADK stack (Keycloak):
- Keycloak runs at `http://keycloak.localtest.me:8080`
- Realm: `adk`
- Pre-configured clients: `adk-ui`, `adk-server`, `kagenti-cli`
- Default seed users depend on the deployment configuration
- **Autologin mode** (`LOCAL_DEV_AUTO_LOGIN=true`) can be used to skip the Keycloak redirect and use a simple credentials form instead

See how the existing ADK UI handles auth at [`apps/adk-ui/src/app/(auth)/auth.ts`](https://github.com/kagenti/adk/blob/main/apps/adk-ui/src/app/(auth)/auth.ts) for a reference implementation using NextAuth, including both the OIDC redirect flow and the local dev autologin credentials provider.

## Using the Access Token

Once the user is authenticated, use the access token for all platform API calls:

- Pass the token to `buildApiClient({ baseUrl, fetch: createAuthenticatedFetch(token) })` — this wraps every fetch with `Authorization: Bearer {token}`.
- The same token is used when creating context tokens via the platform API.
- Context tokens (created in Step 3) are separate — they are passed to agents via A2A message metadata, not used for platform API calls.

## Token Refresh

Access tokens expire. The UI should:

1. Track the token's `expires_in` value from the OIDC token response.
2. Proactively refresh when ~20% of the lifetime remains, using the refresh token.
3. Send a token refresh request to the OIDC token endpoint with `grant_type=refresh_token`.
4. Replace the stored access token with the new one.

If refresh fails (e.g., refresh token expired), redirect the user back to the login page.

See [`apps/adk-ui/src/app/(auth)/utils.ts`](https://github.com/kagenti/adk/blob/main/apps/adk-ui/src/app/(auth)/utils.ts) for the reference token refresh implementation.

## Logout

To log out:

1. Clear the in-memory access token and refresh token.
2. Call the OIDC provider's logout endpoint (from the discovery document's `end_session_endpoint`) to revoke the session at Keycloak.
3. Redirect to the login page.

## Framework Considerations

The OIDC flow implementation depends on the UI framework:

- **Next.js**: Use `next-auth` with an OIDC provider (see existing ADK UI implementation). For autologin, add a Credentials provider alongside.
- **React SPA (Vite)**: Use an OIDC client library like `oidc-client-ts` or `react-oidc-context` for the browser-based flow. For autologin, implement a simple login form that POSTs to the token endpoint with `grant_type=password`.
- **Vanilla / other**: Use `oidc-client-ts` directly or implement the Authorization Code flow with PKCE manually.

Choose the appropriate OIDC library for the user's framework. Do not implement the OAuth flow from scratch when a maintained library exists.

When implementing autologin support, make it conditional on an environment variable (e.g., `LOCAL_DEV_AUTO_LOGIN`). The same OIDC configuration (issuer, client ID, client secret) is used for both flows.

## Anti-Patterns

- Never store access tokens in localStorage or cookies without explicit user approval. Prefer in-memory storage.
- Never expose the client secret in client-side JavaScript. Use PKCE for public clients (SPAs).
- Never skip token refresh. Expired tokens cause silent API failures.
- Never hardcode Keycloak URLs, client IDs, or secrets in source code. Use environment variables.
- Never create context tokens without a valid user access token. The platform validates user permissions before issuing context tokens.
- Never use the user access token where a context token is expected (in A2A message metadata), or vice versa.
