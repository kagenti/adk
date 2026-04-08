# Kagenti ADK

Repo: `kagenti/adk` — use `gh` for GitHub operations.

All commits must be signed off for DCO compliance (`git commit --signoff`).
Use conventional commits: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`.

## Quick Reference

- All testing and linting: `mise run check`
- Fix formatting: `mise run fix`
- Run migrations: `mise run adk-server:migrations:run`
- Git hooks setup: `mise run common:setup:git-hooks`
- Sync embedded code in docs: `mise run docs:fix`

## Code Style

- Python 3.11+, `ruff` for linting and formatting, line length: 120

## Development Rules

- When working in adk-server, always test using the adk-server debugging approach
- Only edit documentation in `docs/development/`, never `docs/stable/`
- For examples workflow (creating, modifying, testing examples): see `CONTRIBUTING.md` § Examples

## Imported Guidelines

@.agent/rules/agent-guidelines.md
@.agent/rules/ui-styling-guidelines.md
