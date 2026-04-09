/**
 * Copyright 2026 © IBM Corp.
 * SPDX-License-Identifier: Apache-2.0
 */

import { buildApiClient, unwrapResult } from '@kagenti/adk';

import { BASE_URL, PROVIDER_ID } from './constants';

export const api = buildApiClient({ baseUrl: BASE_URL });

export async function createContext() {
  const result = await api.createContext({ provider_id: PROVIDER_ID });

  return unwrapResult(result);
}

export async function createContextToken(contextId: string) {
  const result = await api.createContextToken({
    context_id: contextId,
    grant_global_permissions: {
      a2a_proxy: ['*'],
      providers: ['read'],
      llm: ['*'],
      embeddings: ['*'],
    },
    grant_context_permissions: {
      files: ['*'],
      vector_stores: ['*'],
      context_data: ['*'],
    },
  });

  return unwrapResult(result);
}
