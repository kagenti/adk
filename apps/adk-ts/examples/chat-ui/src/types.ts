/**
 * Copyright 2026 © IBM Corp.
 * SPDX-License-Identifier: Apache-2.0
 */

import type { A2AClient } from '@kagenti/adk';

export interface Session {
  client: A2AClient;
  contextId: string;
  metadata: Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'agent';
  text: string;
}
