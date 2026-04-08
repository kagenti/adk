# Copyright 2026 © IBM Corp.
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass

import httpx

logger = logging.getLogger(__name__)

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/kagenti/adk/main/docs/"
DOC_CACHE_TTL = int(os.getenv("DOC_CACHE_TTL", "3600"))

# In-memory cache: key -> (value, timestamp)
_cache: dict[str, tuple[str, float]] = {}


@dataclass
class DocPage:
    path: str
    title: str
    description: str


def _cache_get(key: str) -> str | None:
    entry = _cache.get(key)
    if entry and (time.time() - entry[1]) < DOC_CACHE_TTL:
        return entry[0]
    return None


def _cache_set(key: str, value: str) -> None:
    _cache[key] = (value, time.time())


def _parse_frontmatter(content: str) -> tuple[str, str]:
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return "", ""
    fm = match.group(1)
    title = ""
    description = ""
    for line in fm.splitlines():
        if line.startswith("title:"):
            title = line.split(":", 1)[1].strip().strip("\"'")
        elif line.startswith("description:"):
            description = line.split(":", 1)[1].strip().strip("\"'")
    return title, description


async def _fetch_page_paths(http_client: httpx.AsyncClient) -> list[str]:
    resp = await http_client.get(GITHUB_RAW_BASE + "docs.json")
    resp.raise_for_status()
    data = resp.json()

    paths = []
    for group in data.get("navigation", {}).get("versions", []):
        if group.get("version") != "stable":
            continue
        for section in group.get("groups", []):
            pages = section.get("pages", [])
            for page in pages:
                if isinstance(page, str) and page.startswith("stable/"):
                    paths.append(page)
    return paths


async def _fetch_doc(http_client: httpx.AsyncClient, path: str) -> str | None:
    try:
        resp = await http_client.get(GITHUB_RAW_BASE + path + ".mdx")
        if resp.status_code == 200:
            return resp.text
    except Exception:
        logger.warning("Failed to fetch doc: %s", path)
    return None


async def fetch_doc_manifest(http_client: httpx.AsyncClient) -> list[DocPage]:
    cached = _cache_get("adk_docs:manifest")
    if cached:
        return [DocPage(**p) for p in json.loads(cached)]

    paths = await _fetch_page_paths(http_client)

    import asyncio

    async def fetch_one(path: str) -> DocPage | None:
        content = await _fetch_doc(http_client, path)
        if not content:
            return None
        title, description = _parse_frontmatter(content)
        _cache_set(f"adk_docs:content:{path}", content)
        return DocPage(path=path, title=title or path, description=description or "")

    results = await asyncio.gather(*[fetch_one(p) for p in paths])
    manifest = [r for r in results if r is not None]

    _cache_set("adk_docs:manifest", json.dumps([asdict(p) for p in manifest]))
    return manifest


async def get_doc_content(path: str, http_client: httpx.AsyncClient) -> str | None:
    cached = _cache_get(f"adk_docs:content:{path}")
    if cached:
        return cached

    content = await _fetch_doc(http_client, path)
    if content:
        _cache_set(f"adk_docs:content:{path}", content)
    return content
