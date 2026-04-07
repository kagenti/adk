/**
 * Copyright 2026 © IBM Corp.
 * SPDX-License-Identifier: Apache-2.0
 */

import { createAuthenticatedFetch } from '../../core/create-authenticated-fetch';
import { getA2AEndpointPath } from '../../core/utils/get-a2a-endpoint-path';
import { getAgentCardPath } from '../../core/utils/get-agent-card-path';
import { fetchAgentCard } from './fetch-agent-card';
import { createA2AClient } from './jsonrpc-sse-client';
import type { A2AClient } from './types';

export interface BuildAgentClientParams {
  baseUrl: string;
  providerId: string;
  token: string;
  baseFetch?: typeof fetch;
}

export async function buildAgentClient({
  baseUrl,
  providerId,
  token,
  baseFetch,
}: BuildAgentClientParams): Promise<A2AClient> {
  const fetchImpl = createAuthenticatedFetch(token, baseFetch);

  const agentCardUrl = `${baseUrl}/${getAgentCardPath(providerId)}`;
  const agentCard = await fetchAgentCard(agentCardUrl, fetchImpl);

  const endpointUrl = `${baseUrl}/${getA2AEndpointPath(providerId)}`;
  const extensions = agentCard.capabilities.extensions?.map(({ uri }) => uri);

  return createA2AClient({ endpointUrl, agentCard, fetchImpl, extensions });
}
