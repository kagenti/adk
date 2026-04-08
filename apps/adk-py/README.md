# Kagenti ADK Server SDK

Python SDK for packaging agents for deployment to Kagenti ADK infrastructure.

[![PyPI version](https://img.shields.io/pypi/v/kagenti-adk.svg?style=plastic)](https://pypi.org/project/kagenti-adk/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=plastic)](https://opensource.org/licenses/Apache-2.0)
[![LF AI & Data](https://img.shields.io/badge/LF%20AI%20%26%20Data-0072C6?style=plastic&logo=linuxfoundation&logoColor=white)](https://lfaidata.foundation/projects/)

## Overview

The `kagenti-adk` provides Python utilities for wrapping agents built with any framework (LangChain, CrewAI, BeeAI Framework, etc.) for deployment on Kagenti ADK. It handles the A2A (Agent-to-Agent) protocol implementation, platform service integration, and runtime requirements so you can focus on agent logic.

## Key Features

- **Framework-Agnostic Deployment** - Wrap agents from any framework for Kagenti ADK deployment
- **A2A Protocol Support** - Automatic handling of Agent-to-Agent communication
- **Platform Service Integration** - Connect to Kagenti ADK's managed LLM, embedding, file storage, and vector store services
- **Context Storage** - Manage data associated with conversation contexts

## Installation

```bash
uv add kagenti-adk
```

## Quickstart

```python
import os

from a2a.types import (
    Message,
)
from a2a.utils.message import get_message_text
from kagenti_adk.server import Server
from kagenti_adk.server.context import RunContext
from kagenti_adk.a2a.types import AgentMessage

server = Server()

@server.agent()
async def example_agent(input: Message, context: RunContext):
    """Polite agent that greets the user"""
    hello_template: str = os.getenv("HELLO_TEMPLATE", "Ciao %s!")
    yield AgentMessage(text=hello_template % get_message_text(input))

def run():
    try:
        server.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", 8000)))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
```

Run the agent:

```bash
uv run my_agent.py
```

## Available Extensions

The SDK includes extension support for:

- **Citations** - Source attribution (`CitationExtensionServer`, `CitationExtensionSpec`)
- **Trajectory** - Agent decision logging (`TrajectoryExtensionServer`, `TrajectoryExtensionSpec`)
- **LLM Services** - Platform-managed language models (`LLMServiceExtensionServer`, `LLMServiceExtensionSpec`)
- **Agent Details** - Metadata and UI enhancements (`AgentDetail`)
- **And more** - See [Documentation](https://github.com/kagenti/adk/blob/main/docs/stable/agent-development/overview)

Each extension provides both server-side handlers and A2A protocol specifications for seamless integration with Kagenti ADK's UI and infrastructure.

## Resources

- [Kagenti ADK Documentation](https://github.com/kagenti/adk)
- [GitHub Repository](https://github.com/kagenti/adk)
- [PyPI Package](https://pypi.org/project/kagenti-adk/)

## Contributing

Contributions are welcome! Please see the [Contributing Guide](https://github.com/kagenti/adk/blob/main/CONTRIBUTING.md) for details.

## Support

- [GitHub Issues](https://github.com/kagenti/adk/issues)
- [GitHub Discussions](https://github.com/kagenti/adk/discussions)

---

Developed by contributors to the Kagenti project, this initiative is part of the [Linux Foundation AI & Data program](https://lfaidata.foundation/projects/). Its development follows open, collaborative, and community-driven practices.
