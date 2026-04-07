# Copyright 2026 © IBM Corp.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re

from kagenti_adk.a2a.extensions import Citation


def extract_citations(text: str) -> tuple[list[Citation], str]:
    """
    Extract markdown-style citations [text](url) from text.

    Returns:
        tuple: (list of Citation objects, cleaned text with links replaced by content only)
    """
    citations, offset = [], 0
    pattern = r"\[([^\]]+)\]\(([^)]+)\)"

    for match in re.finditer(pattern, text):
        content, url = match.groups()
        start = match.start() - offset

        citations.append(
            Citation(
                url=url,
                title=url.split("/")[-1].replace("-", " ").title() or content[:50],
                description=content[:100] + ("..." if len(content) > 100 else ""),
                start_index=start,
                end_index=start + len(content),
            )
        )
        offset += len(match.group(0)) - len(content)

    return citations, re.sub(pattern, r"\1", text)
