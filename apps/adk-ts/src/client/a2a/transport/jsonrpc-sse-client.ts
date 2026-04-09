/**
 * Copyright 2026 © IBM Corp.
 * SPDX-License-Identifier: Apache-2.0
 */

import { EventSourceParserStream } from 'eventsource-parser/stream';

import { streamResponseSchema } from '../protocol/schemas';
import type { Task } from '../protocol/types';
import type { A2AClient, CreateA2AClientParams } from './types';

export function createA2AClient({ endpointUrl, agentCard, fetchImpl, extensions }: CreateA2AClientParams): A2AClient {
  const headers = new Headers({ 'Content-Type': 'application/json' });

  if (extensions?.length) {
    headers.set('X-A2A-Extensions', extensions.join(','));
  }

  async function jsonRpcRequest(method: string, params: Record<string, unknown>) {
    const response = await fetchImpl(endpointUrl, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: crypto.randomUUID(),
        method,
        params,
      }),
    });

    if (!response.ok) {
      throw new Error(`A2A request failed: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();

    if (data.error) {
      const err = new Error(data.error.message ?? 'A2A error');
      Object.assign(err, { code: data.error.code, data: data.error.data });
      throw err;
    }

    return data.result;
  }

  return {
    getAgentCard: async () => agentCard,

    async *sendMessageStream(params) {
      const response = await fetchImpl(endpointUrl, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          jsonrpc: '2.0',
          id: crypto.randomUUID(),
          method: 'SendStreamingMessage',
          params,
        }),
      });

      if (!response.ok) {
        throw new Error(`A2A stream request failed: ${response.status} ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error('Response body is empty');
      }

      const eventStream = response.body.pipeThrough(new TextDecoderStream()).pipeThrough(new EventSourceParserStream());
      const reader = eventStream.getReader();

      try {
        while (true) {
          const { done, value: event } = await reader.read();
          if (done) break;

          if (!event.event || event.event === 'message') {
            const data = JSON.parse(event.data);

            if (data.error) {
              const err = new Error(data.error.message ?? 'A2A streaming error');
              Object.assign(err, { code: data.error.code, data: data.error.data });
              throw err;
            }

            if (data.result) {
              const parsed = streamResponseSchema.parse(data.result);
              yield parsed;
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    },

    async getTask(params) {
      return jsonRpcRequest('GetTask', params) as Promise<Task>;
    },

    async cancelTask(params) {
      return jsonRpcRequest('CancelTask', params) as Promise<Task>;
    },
  };
}
