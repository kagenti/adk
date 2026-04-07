/**
 * Copyright 2026 © IBM Corp.
 * SPDX-License-Identifier: Apache-2.0
 */

import { buildAgentClient } from '@kagenti/adk';

import { UnauthenticatedError } from '#api/errors.ts';
import { getBaseUrl } from '#utils/api/getBaseUrl.ts';

import type { A2AClient } from './jsonrpc-client';

export async function getAgentClient(providerId: string, token: string): Promise<A2AClient> {
  return buildAgentClient({
    baseUrl: getBaseUrl(),
    providerId,
    token,
    baseFetch: clientFetch,
  }) as Promise<A2AClient>;
}

async function clientFetch(input: RequestInfo, init?: RequestInit) {
  const response = await fetch(input, init);

  if (!response.ok && response.status === 401) {
    throw new UnauthenticatedError({ message: 'You are not authenticated.', response });
  }

  return response;
}
