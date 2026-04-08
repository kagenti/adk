# Contributing to Kagenti ADK

We are grateful for your interest in joining the Kagenti community and making
a positive impact. Whether you're raising issues, enhancing documentation,
fixing bugs, or developing new features, your contributions are essential to
our success.

## Development Setup

### Agentic Development

For a seamless development experience where an AI coding agent (Claude Code,
Cursor, etc.) manages the full dev lifecycle — running tests, starting/stopping
the platform, executing migrations — you'll want to grant it broad permissions
over Mise tasks. Before doing so, consider running the agent inside a sandbox.

This repo is configured for [locki](https://github.com/JanPokorny/locki) — it
uses the project's own MicroShift VM image (via `locki.toml`). To start a
sandboxed Claude Code session:

```sh
locki claude my-sandbox
```

Install locki with `mise use -g pipx:locki` or `uv tool install locki`.

### Installation

This project uses [Mise-en-place](https://mise.jdx.dev/) as a manager of tool versions (`python`, `uv`, `nodejs`, `pnpm`
etc.), as well as a task runner and environment manager. Mise will download all the needed tools automatically -- you
don't need to install them yourself.

Clone this project, then run these setup steps:

```sh
git clone https://github.com/kagenti/adk.git
cd adk
brew install mise # more ways to install: https://mise.jdx.dev/installing-mise.html
mise trust
mise install
brew install qemu # if not using Brew: install QEMU through some other package manager
```

Install git hooks:

```bash
mise run common:setup:git-hooks
```

After setup, you can use:

- `mise run` to list tasks and select one interactively to run

- `mise <task-name>` to run a task

- `mise x -- <command>` to run a project tool -- for example `mise x -- uv add <package>`

If you want to run tools directly without the `mise x --` prefix, you need to activate a shell hook:

- Bash: `eval "$(mise activate bash)"` (add to `~/.bashrc` to make permanent)

- Zsh: `eval "$(mise activate zsh)"` (add to `~/.zshrc` to make permanent)

- Fish: `mise activate fish | source` (add to `~/.config/fish/config.fish` to make permanent)

- Other shells: [documentation](https://mise.jdx.dev/installing-mise.html#shells)

### Configuration

Edit `[env]` in `mise.local.toml` in the project root ([documentation](https://mise.jdx.dev/environments/)). Run
`mise setup` if you don't see the file.

### Running the platform from source

Starting up the platform using the CLI (`kagenti-adk platform start`, even `mise adk-cli:run -- platform start`)
will use
**published images** by default. To use local images, you need to build them and import them into the platform.

Instead, use:

```shell
mise adk:start
```

This will build the images (`adk-server` and `adk-ui`) and import them to the cluster. You can add other
CLI arguments as you normally would when using `kagenti-adk` CLI, for example:

```shell
mise adk:start --set docling.enabled=true --set oidc.enabled=true
```

To stop or delete the platform use

```shell
mise adk:stop
mise adk:delete
```

For debugging and direct access to kubernetes, setup `KUBECONFIG` and other environment variables using:

```shell
# Activate environment
eval "$(mise run adk:shell)"

# Deactivate environment
deactivate
```

### OAuth/OIDC authentication for local testing

By default, authentication and authorization are disabled.

Starting the platform with OIDC enabled:

```bash
mise adk:start --set auth.enabled=true
```

This will setup keycloak (with no platform users out of the box).

You can add users at <http://keycloak.localtest.me:8080>, by logging in with the admin user (admin:admin in dev)
and going to "Manage realms" -> "Users".

You can promote users by assigning `adk-admin` or `adk-developer` roles to them. Make sure to add a
password in the "Credentials" tab and set their email to verified.

You can also automate this by creating a file `config.yaml`:

```yaml
auth:
  enabled: true
  keycloakProvisionJob:
    enabled: true
    seedUsers:
      - username: admin
        password: admin
        firstName: Admin
        lastName: User
        email: admin@beeai.dev
        roles: ["adk-admin"]
        enabled: true
```

Then run `mise run adk:start -f config.yaml`

**Available endpoints:**

| Service              | HTTP                                |
| -------------------- | ----------------------------------- |
| Keycloak             | `http://keycloak.localtest.me:8080`             |
| Kagenti ADK UI       | `http://adk.localtest.me:8080`                  |
| Kagenti ADK API Docs | `http://adk-api.localtest.me:8080/api/v1/docs`  |

**OIDC configuration:**

- UI: follow `template.env` in `apps/adk-ui` directory (copy to `apps/adk-ui/.env`).
- Server: follow `template.env` in `apps/adk-server` directory (copy to `apps/adk-server/.env`).

### Running and debugging individual components

It's desirable to run and debug (i.e. in an IDE) individual components against the full stack (PostgreSQL,
OpenTelemetry, Arize Phoenix, ...). For this, we include [Telepresence](https://telepresence.io/) which allows rewiring
a Kubernetes container to your local machine. (Note that `sshfs` is not needed, since we don't use it in this setup.)

```sh
mise run adk-server:dev:start
```

This will do the following:

1. Create .env file if it doesn't exist yet (you can add your configuration here)
2. Stop default platform VM ("kagenti-adk") if it exists
3. Start a new VM named "adk-local-dev" separate from the "kagenti-adk" VM used by default
4. Install telepresence into the cluster
   > Note that this will require **root access** on your machine, due to setting up a networking stack.
5. Replace kagenti-adk in the cluster and forward any incoming traffic to localhost

After the command succeeds, you can:

- send requests as if your machine was running inside the cluster. For example:
  `curl http://<service-name>:<service-port>`.

* connect to postgresql using the default credentials `postgresql://adk-user:password@postgresql:5432/adk`
* now you can start your server from your IDE or using `mise run adk-server:run` on port **18333**
* run kagenti-adk using `mise adk-cli:run -- <command>` or HTTP requests to `adk-api.localtest.me:8080` or `localhost:18333`
  - `adk-api.localtest.me:8080` is routed through the cluster networking to the
    kagenti-adk pod, which is replaced by telepresence and forwarded back to your local machine to port 18333
  - `localhost:18333` is where your local platform should be running

To inspect cluster using `kubectl` or `k9s` and lima using `limactl`, activate the dev environment using:

```shell
# Activate dev environment
eval "$(mise run adk-server:dev:shell)"

# Deactivate dev environment
deactivate
```

When you're done you can stop the development cluster and networking using

```shell
mise run adk-server:dev:stop
```

Or delete the cluster entirely using

```shell
mise run adk-server:dev:delete
```

> TIP: If you run into connection issues after sleep or longer period of inactivity
> try `mise run adk-server:dev:reconnect` first. You may not need to clean and restart
> the entire VM

#### Developing tests

To run and develop adk-server tests locally use `mise run adk-server:dev:start --set auth.enabled=true` from above.

> Note:
>
> - Some tests require additional settings (e.g. enabling authentication), see section for tests in `template.env` for more details.
> - Tests will drop your database - you may need to add agents again or reconfigure model

Locally, the default model for tests is configured in `apps/adk-server/tests/conftest.py` (`gpt-oss:20b` from ollama).
Make sure to have this model running locally.

<details>
<summary> Lower-level networking using telepresence directly</summary>

```shell
# Activate environment
eval "$(mise run adk-server:dev:shell)"

# Start platform
mise adk-cli:run -- platform start --vm-name=adk-local-dev # optional --tag [tag] --import-images
mise x -- telepresence helm install
mise x -- telepresence connect

# Receive traffic to a pod by replacing it in the cluster
mise x -- telepresence replace <pod-name>

# More information about how replace/intercept/ingress works: https://telepresence.io/docs/howtos/engage

# Once done, quit Telepresence using:
mise x -- telepresence quit
```

</details>

#### Ollama

If you want to run this local setup against Ollama you must use a special option when setting up the LLM:

```
kagenti-adk model setup --use-true-localhost
```

### Examples

Examples in the `examples/` directory serve as standalone agents, documentation code samples, and e2e tests. See [`examples/README.md`](examples/README.md) for full details.

The `examples/` folder structure mirrors the docs structure. For instance, examples used in `docs/development/agent-integration/forms.mdx` live under `examples/agent-integration/forms/`. Each doc section heading maps to an example name (e.g. "Initial Form Rendering" -> `initial-form-rendering`).

**Modifying an existing example:**

1. Edit the agent code in `examples/<path>/src/<name>/agent.py`
2. Run the related e2e test: `apps/adk-server/tests/e2e/examples/<path>/test_<name>.py`
3. Update docs to sync embedded code: `mise run docs:fix`

**Creating a new example:**

```bash
mise run example:create <path> <description>
```

This scaffolds the example agent and its e2e test. After scaffolding:

1. Implement the agent logic in `examples/<path>/src/<name>/agent.py`
2. Implement the e2e test in `apps/adk-server/tests/e2e/examples/<path>/test_<name>.py`
3. Embed the example in docs using embedme tags:
   ```mdx
   {/* <!-- embedme examples/<path>/src/<name>/agent.py --> */}
   ```
4. Run `mise run docs:fix` to sync the embedded code into docs

> **Naming convention:** The template names the agent function as `<snake_case_name>_example` (e.g. `initial_form_rendering_example`). The example name is derived from the doc section heading where it's used (e.g. "Initial Form Rendering" -> `initial-form-rendering`).

**Running e2e example tests:**

| Command                                 | What it runs                            |
| --------------------------------------- | --------------------------------------- |
| `mise run adk-server:test:e2e`          | Core e2e tests only (excludes examples) |
| `mise run adk-server:test:e2e-examples` | Example e2e tests only                  |

E2e example tests are **not** part of the core e2e suite and don't run on every commit. They run automatically when merged to `main`, or on PRs when you add the `e2e-examples` label.

### Working with migrations

The following commands can be used to create or run migrations in the dev environment above:

- Run migrations: `mise run adk-server:migrations:run`
- Generate migrations: `mise run adk-server:migrations:generate`
- Use Alembic command directly: `mise run adk-server:migrations:alembic`

> NOTE: The dev setup will run the locally built image including its migrations before replacing it with your local
> instance. If new migrations you just implemented are not working, the dev setup will not start properly and you need
> to fix migrations first. You can activate the shell using `eval "$(mise run adk-server:dev:shell)"` and use
> your favorite kubernetes IDE (e.g., k9s or kubectl) to see the migration logs.

### Running individual components

To run Kagenti ADK components in development mode (ensuring proper rebuilding), use the following commands.

#### Server

Build and run server using setup described in [Running the platform from source](#running-the-platform-from-source)
Or use development setup described
in [Running and debugging individual components](#running-and-debugging-individual-components)

#### CLI

```sh
mise adk-cli:run -- agent list
mise adk-cli:run -- agent run website_summarizer "summarize beeai.dev"
```

#### UI

```sh
# run the UI development server:
mise adk-ui:run

# UI is also available from adk-server (in static mode):
mise adk-server:run
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes with tests
4. Run checks: `mise run check`
5. Submit a pull request

Smaller pull requests are typically easier to review and merge. If your pull
request is large, collaborate with the maintainers to find the best way to
divide it.

## Commit Messages

Use conventional commit format:

- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `chore:` Maintenance tasks
- `refactor:` Code refactoring
- `test:` Adding or updating tests

## Releasing

Kagenti ADK is using `main` branch for next version development (integration branch) and `release-v*` branches for stable releases.

The release process consists of three steps:

### Step 1: Cut the release

Ensure that the currently set version in `main` branch is the desired release version. If not, first run `mise run release:set-version <new-version>`.

Run the `release:new` task from the `main` branch:

```shell
mise run release:new
```

This will prepare a new branch `release-vX.Y` (with the version number from `main`), and bump up the version in `main` to the next patch version (e.g., `1.2.3` -> `1.2.4`).

### Step 2: QA & Polish the release on release branch

You can then iteratively polish the release in `release-v*` branch. Do not forget to apply relevant fixes to both the release branch and `main`, e.g. by `git cherrypick`.

To publish a release candidate from the release branch, run `mise run release:publish-rc`. This will publish `X.Y.Z-rcN` version, where `N` is incremented on each RC publish.

Creating new RC will trigger GH action to deploy pre-release version of the package for testing.

### Step 3: Publish

Once the RC makes the QA rounds, publish the final release from the release branch:

```shell
mise run release:publish-stable
```

In addition to publishing the stable version, this action also ensures that the docs in `main` branch are updated to reflect the new version by moving the `docs/development` folder from the release branch to `docs/stable` on `main`.

## Documentation

There are two documentation folders: `docs/stable` and `docs/development`. Due to the nature of Mintlify, docs are deployed from the `main` branch, so we keep `docs/stable` frozen to correspond to the latest stable release. **Only make manual changes in `docs/stable` in order to fix issues with the docs, feature PRs should only edit `docs/development`.**

All PRs **must** either include corresponding documentation in `docs/development`, or include `[x] No Docs Needed` in the PR description. This is checked by GitHub Actions.

Special care needs to be taken with the `docs/development/reference/cli-reference.mdx` file, which is automatically generated. Use `mise run adk-cli:docs` to regenerate this file when modifying the CLI interface.

Try to follow this structure:

- **Elevator pitch:** What value this feature brings to the user.
- **Pre-requisites:** Extra dependencies required on top of Kagenti ADK -- non-default agents, Docker runtime, 3rd party libraries, environment variables like API keys, etc. (Note that `uv` is part of the Kagenti ADK install.)
- **Step-by-step instructions**
- **Troubleshooting:** Common errors and solutions.

Make sure to preview docs locally using: `mise docs:run`. This runs a development server which refreshes as you make changes to the `.mdx` files.

Some code samples in docs are embedded from the `examples/` directory using [embedme](https://github.com/zakhenry/embedme) tags. For these, edit the example agent (not the `.mdx` file directly) and run `mise run docs:fix` to sync. See [Examples](#examples) for the full workflow.

## Certificate of Origin

All commits **must** include a `Signed-off-by` trailer (Developer Certificate
of Origin). Use the `-s` flag when committing:

```bash
git commit -s -m "feat: add new feature"
```

By contributing to this project you agree to the
[Developer Certificate of Origin](https://developercertificate.org/) (DCO).

## Licensing

Kagenti ADK is [Apache 2.0 licensed](LICENSE) and we accept contributions
via GitHub pull requests.
