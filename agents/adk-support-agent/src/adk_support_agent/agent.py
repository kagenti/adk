# Copyright 2026 © IBM Corp.
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import os
from typing import Annotated

import httpx
import openai
from a2a.types import AgentSkill, Message
from a2a.utils.message import get_message_text
from kagenti_adk.a2a.extensions import (
    AgentDetail,
    CitationExtensionServer,
    CitationExtensionSpec,
    LLMServiceExtensionServer,
    LLMServiceExtensionSpec,
    TrajectoryExtensionServer,
    TrajectoryExtensionSpec,
)
from kagenti_adk.a2a.types import AgentMessage
from kagenti_adk.server import Server
from kagenti_adk.server.context import RunContext

from .citations import extract_citations
from .docs import GITHUB_RAW_BASE, fetch_doc_manifest, get_doc_content

logger = logging.getLogger(__name__)

server = Server()

DOCS_BASE_URL = "https://kagenti.github.io/adk/stable/"

STAGE1_SYSTEM = """\
You are a document retrieval assistant for Kagenti ADK documentation.
Given a user question, select which documentation pages are most relevant.
Return ONLY a JSON array of path strings, e.g. ["stable/introduction/welcome"].
Select 1-5 pages. If the question is not about ADK, return []."""

STAGE2_SYSTEM = """\
You are the Kagenti ADK Support Assistant. Answer the user's question using ONLY \
the provided documentation. Be precise and include code examples from the docs when \
relevant. If the documentation does not contain the answer, say so clearly.

## Citation Requirements
When referencing information from a documentation page, you MUST cite it using markdown format:
- Format: [descriptive text](URL)
- The URL for each doc page is provided in the documentation section headers.
- Place citations inline where the information is referenced.

Example: According to the [deployment guide](https://kagenti.github.io/adk/stable/deploy-agents/deploy-your-agents), \
you can use `kagenti-adk add` to deploy your agent."""


def _get_llm_config(llm: LLMServiceExtensionServer):
    if llm and llm.data and llm.data.llm_fulfillments:
        config = llm.data.llm_fulfillments.get("default")
        if config:
            return config
    raise RuntimeError(
        "No LLM configured. Set LLM_API_BASE, LLM_API_KEY, and LLM_MODEL env vars for local dev."
    )


def _format_manifest(manifest) -> str:
    lines = []
    for i, doc in enumerate(manifest, 1):
        lines.append(f"{i}. {doc.title} — {doc.description} [path: {doc.path}]")
    return "\n".join(lines)


def _doc_url(path: str) -> str:
    """Convert a doc path like 'stable/introduction/welcome' to its full URL."""
    return DOCS_BASE_URL + path.removeprefix("stable/")


async def _build_history(context: RunContext) -> list[dict]:
    messages = []
    try:
        async for item in context.load_history():
            msg = item if isinstance(item, Message) else getattr(item, "message", None)
            if msg is None:
                continue
            text = get_message_text(msg)
            if not text:
                continue
            role = "assistant" if hasattr(item, "artifact_id") else "user"
            messages.append({"role": role, "content": text})
    except Exception:
        pass
    return messages


async def _select_docs(
    client: openai.AsyncOpenAI, model: str, manifest, question: str
) -> list[str]:
    manifest_text = _format_manifest(manifest)
    try:
        resp = await client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": STAGE1_SYSTEM},
                {
                    "role": "user",
                    "content": f"Documentation pages:\n{manifest_text}\n\nUser question: {question}",
                },
            ],
        )
        content = resp.choices[0].message.content or "[]"
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        paths = json.loads(content)
        if isinstance(paths, list):
            return [p for p in paths if isinstance(p, str)]
    except Exception:
        logger.warning("Stage 1 doc selection failed, falling back to top 5 docs")
    return [doc.path for doc in manifest[:5]]


@server.agent(
    name="ADK Support Assistant",
    version="1.0.0",
    default_input_modes=["text", "text/plain"],
    default_output_modes=["text", "text/plain"],
    detail=AgentDetail(
        interaction_mode="multi-turn",
        user_greeting="Hi! I'm the ADK Support Assistant. Ask me anything about building and deploying agents with Kagenti ADK.",
        framework="Python",
        source_code_url="https://github.com/kagenti/adk-support-agent",
    ),
    skills=[
        AgentSkill(
            id="adk-docs",
            name="ADK Documentation",
            description="Answers questions about Kagenti ADK by searching the official documentation. Covers agent development, deployment, extensions, MCP, RAG, and more.",
            tags=["adk", "documentation", "support", "kagenti"],
            examples=[
                "How do I deploy my agent to Kagenti?"
            ],
        )
    ],
)
async def adk_support(
    input: Message,
    context: RunContext,
    llm: Annotated[LLMServiceExtensionServer, LLMServiceExtensionSpec.single_demand()],
    trajectory: Annotated[TrajectoryExtensionServer, TrajectoryExtensionSpec()],
    citation: Annotated[CitationExtensionServer, CitationExtensionSpec()],
):
    """Answers questions about Kagenti ADK using the official documentation."""
    await context.store(input)
    user_input = get_message_text(input)

    llm_config = _get_llm_config(llm)
    client = openai.AsyncOpenAI(
        api_key=llm_config.api_key, base_url=llm_config.api_base
    )
    model = llm_config.api_model

    yield trajectory.trajectory_metadata(
        title="Initializing", content="Loading documentation manifest"
    )

    async with httpx.AsyncClient(
        base_url=GITHUB_RAW_BASE, timeout=30.0
    ) as http_client:
        manifest = await fetch_doc_manifest(http_client)
        history = await _build_history(context)

        # Stage 1: LLM picks relevant docs
        yield trajectory.trajectory_metadata(
            title="Selecting docs", content="Asking LLM to select relevant documentation pages"
        )
        relevant_paths = await _select_docs(client, model, manifest, user_input)
        logger.info("Selected docs: %s", relevant_paths)

        # Build summary of selected docs for trajectory
        selected_titles = []
        for path in relevant_paths:
            title = next((d.title for d in manifest if d.path == path), path)
            selected_titles.append(title)
        yield trajectory.trajectory_metadata(
            title="Docs selected",
            content=f"Found {len(relevant_paths)} relevant page(s):\n" + "\n".join(f"- {t}" for t in selected_titles),
        )

        # Fetch doc contents
        doc_contents = []
        for path in relevant_paths:
            content = await get_doc_content(path, http_client)
            if content:
                title = next((d.title for d in manifest if d.path == path), path)
                doc_contents.append((title, path, content))

    # Stage 2: Stream the answer
    yield trajectory.trajectory_metadata(
        title="Generating answer",
        content=f"Streaming response using {len(doc_contents)} doc(s) as context",
    )

    docs_text = ""
    for title, path, content in doc_contents:
        url = _doc_url(path)
        docs_text += f"\n---\n## {title}\nURL: {url}\n{content}\n"

    messages = [
        {"role": "system", "content": STAGE2_SYSTEM},
        {"role": "user", "content": f"Documentation:\n{docs_text}"},
        {"role": "assistant", "content": "I've read the documentation. I'm ready to answer your question."},
    ]
    messages.extend(history)
    messages.append({"role": "user", "content": user_input})

    stream = await client.chat.completions.create(
        model=model, temperature=0, messages=messages, stream=True
    )

    buffer = ""
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content or ""
        if delta:
            buffer += delta
            yield delta

    # Extract citations from the complete response
    citations, clean_text = extract_citations(buffer)

    # Store final message with citation metadata
    message = AgentMessage(
        text=clean_text,
        metadata=(citation.citation_metadata(citations=citations) if citations else None),
    )
    await context.store(message)

    if citations:
        yield citation.citation_metadata(citations=citations)

    yield trajectory.trajectory_metadata(
        title="Complete",
        content=f"Response delivered with {len(citations)} citation(s)",
    )


def run():
    try:
        server.run(
            host=os.getenv("HOST", "127.0.0.1"),
            port=int(os.getenv("PORT", 8000)),
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
