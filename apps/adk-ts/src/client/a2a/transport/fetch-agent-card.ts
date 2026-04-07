/**
 * Copyright 2026 © IBM Corp.
 * SPDX-License-Identifier: Apache-2.0
 */

import { agentCardSchema } from '../protocol/schemas';
import type { AgentCard } from '../protocol/types';

export async function fetchAgentCard(url: string, fetchImpl: typeof fetch): Promise<AgentCard> {
  const response = await fetchImpl(url);

  if (!response.ok) {
    throw new Error(`Failed to fetch agent card: ${response.status} ${response.statusText}`);
  }

  const data = await response.json();
  return agentCardSchema.parse(data);
}
