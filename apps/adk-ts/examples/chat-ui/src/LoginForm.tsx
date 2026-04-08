/**
 * Copyright 2026 © IBM Corp.
 * SPDX-License-Identifier: Apache-2.0
 */

import { type SubmitEvent, useState } from 'react';

import { login } from './auth';

export function LoginForm({ onLogin }: { onLogin: (accessToken: string) => void }) {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const tokens = await login(username, password);
      onLogin(tokens.access_token);
    } catch {
      setError('Login failed. Check your credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="app">
      <h1 className="heading">Kagenti ADK Chat Example</h1>

      <form className="login-form" onSubmit={handleSubmit}>
        <input
          className="input"
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Username"
        />

        <input
          className="input"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
        />

        <button className="button" type="submit" disabled={isLoading}>
          {isLoading ? 'Logging in…' : 'Log in'}
        </button>

        {error && <p className="error">{error}</p>}
      </form>
    </main>
  );
}
