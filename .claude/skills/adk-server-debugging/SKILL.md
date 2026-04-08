---
name: adk-server-debugging
description: Instructions for debugging adk-server during development
---

ADK server runs in a Kubernetes cluster inside a Lima VM. For local development, the server runs on your machine with Telepresence routing cluster traffic to it.

## Getting the Environment Ready

Run `mise run dev:ensure` to start everything needed for server development. This is idempotent — safe to run repeatedly. It will:

1. Start the Lima VM and platform if not running
2. Connect Telepresence if not connected
3. Start the local server in the background if not running
4. Set up postgres port-forwarding

Check status anytime with `mise run dev:status`.

## `.env` Configuration

The server reads from `apps/adk-server/.env`. If it doesn't exist, copy from `template.env`:

```bash
cp apps/adk-server/template.env apps/adk-server/.env
```

Template defaults work for development. For running tests, add:

```
DB_URL=postgresql+asyncpg://adk-user:password@localhost:5432/adk
```

## Commands

| Action | Command |
|--------|---------|
| Ensure dev env is ready | `mise run dev:ensure` |
| Check environment status | `mise run dev:status` |
| Run server manually (if not via dev:ensure) | `mise run adk-server:run` |
| Run a specific test | `cd apps/adk-server && uv run pytest -k 'test_name'` |
| Run CLI | `mise run adk-cli:run -- <command>` |
| Stop local processes (keep VM) | `mise run dev:stop` |

## Troubleshooting

- **Server won't start**: Check `~/.kagenti/adk/logs/adk-server.log` for errors.
- **Telepresence issues**: Run `mise run dev:stop` then `mise run dev:ensure` to reconnect.
- **Port conflicts**: `mise run dev:stop` kills processes on ports 18333, 3000, 5432, 6379.
