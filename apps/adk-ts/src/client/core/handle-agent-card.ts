/**
 * Copyright 2026 © IBM Corp.
 * SPDX-License-Identifier: Apache-2.0
 */

import { oauthExtension, oauthRequestExtension } from '../a2a/extensions/auth/oauth';
import { secretsExtension } from '../a2a/extensions/auth/secrets';
import { embeddingExtension } from '../a2a/extensions/services/embedding';
import { formExtension } from '../a2a/extensions/services/form';
import { llmExtension } from '../a2a/extensions/services/llm';
import { mcpExtension } from '../a2a/extensions/services/mcp';
import { platformApiExtension } from '../a2a/extensions/services/platform-api';
import type { AgentCapabilities } from '../a2a/protocol/types';
import { extractServiceExtensionDemands } from './extensions/extract';
import { fulfillServiceExtensionDemand } from './extensions/fulfill';
import type { Fulfillments } from './extensions/types';

const mcpExtensionExtractor = extractServiceExtensionDemands(mcpExtension);
const llmExtensionExtractor = extractServiceExtensionDemands(llmExtension);
const embeddingExtensionExtractor = extractServiceExtensionDemands(embeddingExtension);
const oauthExtensionExtractor = extractServiceExtensionDemands(oauthExtension);
const secretExtensionExtractor = extractServiceExtensionDemands(secretsExtension);
const formExtensionExtractor = extractServiceExtensionDemands(formExtension);

const fulfillMcpDemand = fulfillServiceExtensionDemand(mcpExtension);
const fulfillLlmDemand = fulfillServiceExtensionDemand(llmExtension);
const fulfillEmbeddingDemand = fulfillServiceExtensionDemand(embeddingExtension);
const fulfillOAuthDemand = fulfillServiceExtensionDemand(oauthExtension);
const fulfillSecretDemand = fulfillServiceExtensionDemand(secretsExtension);
const fulfillFormDemand = fulfillServiceExtensionDemand(formExtension);

export const handleAgentCard = (agentCard: { capabilities: AgentCapabilities }) => {
  const extensions = agentCard.capabilities.extensions ?? [];

  const llmDemands = llmExtensionExtractor(extensions);
  const embeddingDemands = embeddingExtensionExtractor(extensions);
  const mcpDemands = mcpExtensionExtractor(extensions);
  const oauthDemands = oauthExtensionExtractor(extensions);
  const secretDemands = secretExtensionExtractor(extensions);
  const formDemands = formExtensionExtractor(extensions);

  const resolveMetadata = async (fulfillments: Fulfillments) => {
    let fulfilledMetadata: Record<string, unknown> = {};

    if (fulfillments.getContextToken) {
      fulfilledMetadata = platformApiExtension(fulfilledMetadata, fulfillments.getContextToken());
    }

    if (llmDemands && fulfillments.llm) {
      fulfilledMetadata = fulfillLlmDemand(fulfilledMetadata, await fulfillments.llm(llmDemands));
    }

    if (embeddingDemands && fulfillments.embedding) {
      fulfilledMetadata = fulfillEmbeddingDemand(fulfilledMetadata, await fulfillments.embedding(embeddingDemands));
    }

    if (mcpDemands && fulfillments.mcp) {
      fulfilledMetadata = fulfillMcpDemand(fulfilledMetadata, await fulfillments.mcp(mcpDemands));
    }

    if (oauthDemands && fulfillments.oauth) {
      fulfilledMetadata = fulfillOAuthDemand(fulfilledMetadata, await fulfillments.oauth(oauthDemands));
    }

    if (secretDemands && fulfillments.secrets) {
      fulfilledMetadata = fulfillSecretDemand(fulfilledMetadata, await fulfillments.secrets(secretDemands));
    }

    if (formDemands && fulfillments.form) {
      fulfilledMetadata = fulfillFormDemand(fulfilledMetadata, await fulfillments.form(formDemands));
    }

    const oauthRedirectUri = fulfillments.oauthRedirectUri?.();

    if (oauthRedirectUri) {
      fulfilledMetadata = {
        ...fulfilledMetadata,
        [oauthRequestExtension.getUri()]: {
          redirect_uri: oauthRedirectUri,
        },
      };
    }

    return fulfilledMetadata;
  };

  return {
    resolveMetadata,
    demands: {
      llmDemands,
      embeddingDemands,
      mcpDemands,
      oauthDemands,
      secretDemands,
      formDemands,
    },
  };
};
