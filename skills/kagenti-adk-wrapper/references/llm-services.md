# LLM / Services Wiring Reference (Step 5)

Use this reference for wiring LLM and service configuration through Kagenti ADK extensions.

**OpenAI-compatible interface required.** The agent must be designed to work with an OpenAI-compatible interface. If the original agent uses a different LLM provider (e.g., Anthropic, Google), you must install the necessary library (e.g., `langchain-openai`) and use that provider class, passing the configuration received from the LLM extension.

**Do not read API keys from environment variables.** Use Kagenti ADK platform extensions to receive LLM configuration at runtime.
_(Note: Sometimes the exact structure of the credentials provided by the extension can only be fully explored and validated by running the agent and inspecting the injected objects)._

Add `llm: Annotated[LLMServiceExtensionServer, LLMServiceExtensionSpec.single_demand()]` as an agent function parameter. Extract the config from `llm.data.llm_fulfillments["default"]` and pass `api_key`, `api_base`, `api_model` explicitly to the original agent.

If the `default` fulfillment is missing, declare a secrets parameter (for example `secrets: Annotated[SecretsExtensionServer, SecretsExtensionSpec.single_demand(name="...")]`), request required secrets through that declared parameter, then construct fulfillment-compatible values and pass `api_key`, `api_base`, and `api_model` explicitly.

If the original agent reads env vars for API keys internally, refactor it so keys are passed as explicit parameters instead.
Always pass runtime LLM config explicitly, avoid provider/default fallback chains, and fail fast with a clear error if required values are missing.

## Examples

See the [LLM access example](https://github.com/kagenti/adk/blob/main/examples/agent-integration/llm-proxy-service/llm-access/src/llm_access/agent.py) on GitHub for a real example of LLM extension wiring.

## Anti-Patterns

- Do not reference `secrets.request_secrets(params=...)` unless a `secrets` extension parameter is declared on the agent function.
- Do not skip the docs/examples and improvise imports or extension usage.
- Do not read model/API key/base URL from env vars when LLM extension is available.
- Do not rewrite `api_base` heuristically unless the official docs explicitly require it.
- Do not use a generic model as `suggested` — use the same model identifier as the original agent.
