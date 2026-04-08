/**
 * Copyright 2026 © IBM Corp.
 * SPDX-License-Identifier: Apache-2.0
 */

import { OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, OIDC_ISSUER } from './constants';

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

export async function login(username: string, password: string): Promise<TokenResponse> {
  const tokenEndpoint = `${OIDC_ISSUER}/protocol/openid-connect/token`;

  const response = await fetch(tokenEndpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'password',
      client_id: OIDC_CLIENT_ID,
      client_secret: OIDC_CLIENT_SECRET,
      username,
      password,
      scope: 'openid email profile',
    }),
  });

  if (!response.ok) {
    throw new Error('Invalid credentials');
  }

  return response.json();
}
