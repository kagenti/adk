/**
 * Copyright 2026 © IBM Corp.
 * SPDX-License-Identifier: Apache-2.0
 */

import type { A2AClient, ContextToken, Message } from '@kagenti/adk';
import { buildLLMExtensionFulfillmentResolver, handleAgentCard } from '@kagenti/adk';

import type { createApi } from './api';
import type { ChatMessage } from './types';

export function createMessage({ role, text }: Pick<ChatMessage, 'role' | 'text'>): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role,
    text,
  };
}

export async function resolveAgentMetadata({
  api,
  client,
  contextToken,
}: {
  api: ReturnType<typeof createApi>;
  client: A2AClient;
  contextToken: ContextToken;
}) {
  const agentCard = await client.getAgentCard();
  const { resolveMetadata } = handleAgentCard(agentCard);
  const llmResolver = buildLLMExtensionFulfillmentResolver(api, contextToken);
  const agentMetadata = await resolveMetadata({ llm: llmResolver });

  return agentMetadata;
}

export function extractTextFromMessage(message: Message | undefined) {
  const text = message?.parts
    .filter((part) => 'text' in part)
    .map((part) => (part as { text: string }).text)
    .join('\n');

  return text;
}
