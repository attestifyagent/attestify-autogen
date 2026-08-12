# attestify-autogen

> Governed AI loop execution for [AutoGen](https://microsoft.github.io/autogen/) — signed receipts, audit trails, and x402 payments on Base.

## Installation

```bash
pip install attestify-autogen
```

## Quick Start

```python
from attestify_autogen import register_attestify_functions
from autogen import AssistantAgent, UserProxyAgent
import os

assistant = AssistantAgent(
    name="assistant",
    llm_config={"config_list": [{"model": "gpt-4o", "api_key": os.environ["OPENAI_API_KEY"]}]},
    system_message=(
        "You are an operations agent with access to the Attestify governed execution layer. "
        "Always confirm the loop_id and cost from any attestify_run_loop call."
    ),
)

user_proxy = UserProxyAgent(
    name="user",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=5,
)

register_attestify_functions(
    assistant=assistant,
    executor=user_proxy,
    api_key=os.environ["ATTESTIFY_API_KEY"],
)

user_proxy.initiate_chat(
    assistant,
    message="Summarise the latest AI agent governance trends and give me the receipt ID."
)
```

## Available Functions

| Function | Description | Plan |
|---|---|---|
| `attestify_run_loop` | Submit a task to the governed loop router | All |
| `attestify_get_dashboard` | Run count, quota, plan tier, recent receipts | Builder+ |
| `attestify_get_recent_loops` | List recent loop receipts | All |
| `attestify_get_receipt` | Retrieve a verified receipt by loop_id | All |
| `attestify_get_control_tower` | Enterprise governance data & cross-tenant visibility | Enterprise |

## Links

- [Attestify OS](https://attestifyos.com)
- [Documentation](https://attestifyos.com/docs)
- [Get an API key](https://attestifyos.com/dashboard)
- [MCP Package](../../mcp-package/)
- [GitHub](https://github.com/attestifyagent/attestify-os)
