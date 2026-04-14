ARG UV_VERSION=0.11.2
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv
FROM python:3.13-slim
COPY --from=uv /uv /bin/uv
COPY . /app/.
WORKDIR /app/agents/adk-support-agent
RUN UV_COMPILE_BYTECODE=1 HOME=/tmp uv sync --no-cache --link-mode copy
ENV PRODUCTION_MODE=True
CMD ["/app/agents/adk-support-agent/.venv/bin/server"]
