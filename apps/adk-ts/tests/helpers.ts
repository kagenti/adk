/**
 * Copyright 2026 © IBM Corp.
 * SPDX-License-Identifier: Apache-2.0
 */

import net from 'net';

import type { A2AClient } from '../src/client/a2a/transport';
import { createA2AClient as createA2ATransportClient, fetchAgentCard } from '../src/client/a2a/transport';
import { buildMessageBuilder, handleAgentCard } from '../src/client/core';

export async function getRandomPort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = net.createServer();

    server.listen(0, () => {
      const address = server.address();

      if (address && typeof address === 'object') {
        const port = address.port;

        server.close(() => resolve(port));
      } else {
        reject(new Error('Failed to get port'));
      }
    });

    server.on('error', reject);
  });
}

export async function createA2AClient(baseUrl: string) {
  const agentCardUrl = `${baseUrl}/.well-known/agent-card.json`;
  const agentCard = await fetchAgentCard(agentCardUrl, fetch);

  const endpointUrl = `${baseUrl}/`;
  const extensions = agentCard.capabilities.extensions?.map(({ uri }) => uri);
  const client: A2AClient = createA2ATransportClient({ endpointUrl, agentCard, fetchImpl: fetch, extensions });

  const { demands } = handleAgentCard(agentCard);
  const createMessage = buildMessageBuilder(agentCard);

  return {
    client,
    agentCard,
    demands,
    createMessage,
  };
}
