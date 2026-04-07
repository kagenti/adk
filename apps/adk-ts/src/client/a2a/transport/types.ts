/**
 * Copyright 2026 © IBM Corp.
 * SPDX-License-Identifier: Apache-2.0
 */

import type { AgentCard, Message, StreamResponse, Task } from '../protocol/types';

export interface A2AClient {
  getAgentCard(): Promise<AgentCard>;
  sendMessageStream(params: {
    message: Message;
    configuration?: Record<string, unknown>;
    metadata?: Record<string, unknown>;
  }): AsyncIterable<StreamResponse>;
  getTask(params: { id: string }): Promise<Task>;
  cancelTask(params: { id: string }): Promise<Task>;
}

export interface CreateA2AClientParams {
  endpointUrl: string;
  agentCard: AgentCard;
  fetchImpl: typeof fetch;
  extensions?: string[];
}
