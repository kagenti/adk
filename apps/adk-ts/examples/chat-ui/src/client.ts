/**
 * Copyright 2026 © IBM Corp.
 * SPDX-License-Identifier: Apache-2.0
 */

import { buildAgentClient } from '@kagenti/adk';
import { useEffect, useState } from 'react';

import { createApi, createContext, createContextToken } from './api';
import { BASE_URL, PROVIDER_ID } from './constants';
import type { Session } from './types';
import { extractTextFromMessage, resolveAgentMetadata } from './utils';

async function ensureSession(accessToken: string) {
  if (!BASE_URL || !PROVIDER_ID) {
    throw new Error(`Missing required environment variables.`);
  }

  const api = createApi(accessToken);
  const context = await createContext(api);
  const contextToken = await createContextToken(api, context.id);
  const client = await buildAgentClient({
    baseUrl: BASE_URL,
    providerId: PROVIDER_ID,
    token: contextToken.token,
  });
  const metadata = await resolveAgentMetadata({ api, client, contextToken });

  return {
    client,
    contextId: context.id,
    metadata,
  };
}

export function useAgent(accessToken: string) {
  const [session, setSession] = useState<Session>();
  const [isInitializing, setIsInitializing] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (session) {
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        setIsInitializing(true);

        const session = await ensureSession(accessToken);

        if (cancelled) {
          return;
        }

        setSession(session);
      } catch (error) {
        if (cancelled) {
          return;
        }

        const message = error instanceof Error ? error.message : 'Failed to connect to agent.';

        setError(message);
      } finally {
        if (!cancelled) {
          setIsInitializing(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [session, accessToken]);

  const sendMessage = async ({ text }: { text: string }) => {
    if (!session) {
      throw new Error('Agent is not ready yet.');
    }

    const { client, contextId, metadata } = session;

    const runStream = async () => {
      const stream = client.sendMessageStream({
        message: {
          messageId: crypto.randomUUID(),
          role: 'ROLE_USER',
          contextId,
          parts: [{ text }],
          metadata,
        },
      });

      let agentText = '';

      for await (const event of stream) {
        if ('statusUpdate' in event && event.statusUpdate) {
          const text = extractTextFromMessage(event.statusUpdate.status?.message);

          if (text) {
            agentText += text;
          }
        }

        if ('message' in event && event.message) {
          const text = extractTextFromMessage(event.message);

          if (text) {
            agentText += text;
          }
        }
      }

      return {
        text: agentText,
      };
    };

    return await runStream();
  };

  return {
    session,
    isInitializing,
    error,
    sendMessage,
  };
}
