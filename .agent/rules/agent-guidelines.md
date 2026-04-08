# Kagenti ADK Project Guidelines

Decision tables and commands for common tasks.

## 1. Project Structure & Task Runner

- **Monorepo** with multiple projects (apps, agents, generic packages).
- **Task runner**: [mise](https://mise.jdx.dev).
- **Python**: Each project has its own `.venv`. Use `uv run` to execute commands (e.g. `uv run pytest`).

## 2. Development Environment

### Environment Tiers

| Tier | What's Running | Use Case | How to Start |
|------|---------------|----------|--------------|
| 0 | Nothing | adk-py, unit tests, linting, formatting, helm | Run checks directly |
| 1 | Lima VM + MicroShift + platform | Base infrastructure (prerequisite for 2+) | (automatic) |
| 2 | Tier 1 + telepresence + local server on :18333 | Server dev, debugging, migrations | `mise run dev:ensure` |
| 3 | Tier 2 + UI dev server on :3000 (hot-reload) | UI development | `mise run dev:ensure --with-ui` |

`dev:ensure` is **idempotent** — safe to run anytime. Takes ~10 minutes on a cold start. Extra CLI args pass through to `adk-server:dev:start` → `adk:start` (e.g. `--set auth.enabled=true`). Multiple `--set` flags can be combined.

If the user doesn't specify what they need, ask before running `dev:ensure`:
- UI dev server? (`--with-ui`)
- Auth enabled? (`--set auth.enabled=true`)
- Static UI disabled? (`--set ui.enabled=false`)

### Other Commands

- `mise run dev:status` — show what's running.
- `mise run dev:stop` — stop everything including the VM.
- `curl localhost:18333/healthcheck` — quick server liveness check (direct local port). `adk-api.localtest.me:8080` also works — it routes through cluster networking via telepresence to the same server.

### `.env` Configuration

The server reads configuration from `apps/adk-server/.env`.

- If `.env` doesn't exist, copy from `apps/adk-server/template.env`. Template defaults work for development.
- **Running tests directly** (via `uv run pytest`, not via `mise run` tasks): add `DB_URL=postgresql+asyncpg://adk-user:password@localhost:5432/adk` — tests connect to Postgres directly, not through telepresence. The `mise run` test tasks set this automatically.
- **Auth-enabled testing**: uncomment auth settings at the bottom of `.env` (copied from `template.env`).
- **Never overwrite** a `.env` file without reading it first — it may contain custom values.

### Safety Rules

- **Never** run `adk:delete` or `adk-server:dev:delete` without asking the developer — these destroy the VM, which takes longer to recreate.

## 3. Testing Strategies

### adk-server

Tests use pytest markers. **Always use a marker** — bare `uv run pytest` hits all tests including integration/e2e that fail without infrastructure.

| Marker | mise task | Direct (from `apps/adk-server`) | Infrastructure |
|---|---|---|---|
| `unit` | `mise run adk-server:test:unit` | `uv run pytest -m unit` | None |
| `integration` | `mise run adk-server:test:integration` | `uv run pytest -m integration` | Postgres (+ Redis for some). `dev:ensure` first. |
| `e2e` | `mise run adk-server:test:e2e` | `uv run pytest -m e2e` | Full stack. `dev:ensure` first. |

- `mise run adk-server:test` runs unit tests only. The integration and e2e mise tasks spin up their own infrastructure automatically.
- When running tests directly (`uv run pytest`), prefer specific tests (`-k 'test_name'`), not the full integration/e2e suite.
- Connection errors at fixture setup = infrastructure not running → `mise run dev:ensure`, don't chase code bugs.

### adk-py

Tests are independent of the dev stack. Run from `apps/adk-py`:

- Direct: `uv run pytest` (all tests, current Python)
- Via mise: `mise run adk-py:test-all` (defaults to Python 3.14, configurable with `--python <version>`)

## 4. Database Migrations

- **Stack**: SQLAlchemy Core + Alembic.
- **Workflow**:
  1. **Generate**: `mise run adk-server:migrations:generate` (must be in dev mode). **Never write migrations from scratch.**
  2. **Modify**: specific migration files after generation if needed.
  3. **Execute**: `mise run adk-server:migrations:run` (in dev mode).

## 5. Helm Chart Development

- **Templating**: Always use `--set encryptionKey="dummy"` when running `helm template` to avoid intentional failures.

## 6. Architecture Overview

The platform consists of multiple K8s microservices:

### Kagenti ADK server (`adk-server`)

- **Core Orchestrator**: Manages APIs for agents, files, vector stores, and permissions (Context Service/JWT).
- **Cluster Management**: Uses `kr8s` client to create K8s objects (deployments, services, secrets, build jobs, MCP servers).
- **Infrastructure Integrations**:
  - **Postgres**: Relational DB, Vector Store (pgvector), Task Queue (procrastinate), Secret Store (encrypted).
  - **SeaweedFS**: S3-compatible storage.
  - **Docling**: Text extraction service.
  - **Redis**: Optional caching.
- **Gateways**:
  - **Model Gateway**: Proxies OpenAI API.
  - **Agent Gateway**: Exposes A2A (Agent-to-Agent) API which proxies communication to agents. All communication to agents must go through this proxy.
- **Background Workers**: Uses procrastinate package to manage background workers and crons in postgresql.
- **Permission System**: We use role-based permissions with caveats, this is described in detail in `docs/development/custom-ui/permissions-and-tokens.mdx`

### Kagenti ADK UI (`adk-ui`)

- JavaScript frontend communicating with `adk-server`.
- **Development**: Runs locally on `localhost:3000` or inside the cluster.

### Kagenti ADK (`adk-py`)

- Python library for agents to interact with the server API.

### Infrastructure & Observability

- **Agents**: Managed by Kubernetes (scale 0-1).
- **Observability**: Otel-collector pushing traces to Arize Phoenix.
- **Auth**: Supports multiple configurations, read `docs/development/deployment-guide.mdx` if necessary.

## 7. General Best Practices

- **Commands**: Construct commands relative to the project root or verify `cwd` before running.
- **Verification**: If unsure about environment state, check `/healthcheck` or ask the user.
- **Docs**: You can read and modify documentation in the `docs/development` folder to get more information
