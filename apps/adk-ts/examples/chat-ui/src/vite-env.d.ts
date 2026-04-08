/**
 * Copyright 2026 © IBM Corp.
 * SPDX-License-Identifier: Apache-2.0
 */

interface ImportMetaEnv {
  readonly VITE_ADK_BASE_URL: string;
  readonly VITE_ADK_PROVIDER_ID: string;
  readonly VITE_OIDC_ISSUER: string;
  readonly VITE_OIDC_CLIENT_ID: string;
  readonly VITE_OIDC_CLIENT_SECRET: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
