# attestify-autogen

> Governed AI loop execution for [AutoGen](https://microsoft.github.io/autogen/) — signed receipts, audit trails, x402 payments on Base, and [Attestify Trust](https://attestifyos.com/trust) (no-wallet agent identity + signed evidence).

## Installation

```bash
pip install attestify-autogen
```

Trust functions additionally need `cryptography` — install with `pip install attestify-autogen[trust]`; everything else works without it.

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
| `attestify_trust_submit_evidence` | Sign and submit evidence of real work — free, no wallet | All (Trust configured) |
| `attestify_trust_verify` | Independently verify any Trust receipt by ID | Public, no key |

## Attestify Trust — no-wallet agent identity + signed evidence

A separate concern from the Router functions above: no x402, no lanes, no spend. Register once, then the assistant can sign proof of what it actually did.

```python
from attestify_autogen import provision_trust_agent, register_attestify_functions
import os

# ONE TIME, outside any conversation — never let the agent call this itself.
# A fresh identity per run breaks the agent's own verified-active streak
# and adds noise to Attestify's public census instead of a real number.
creds = provision_trust_agent(
    api_key=os.environ["ATTESTIFY_API_KEY"],
    display_name="AutoGen Assistant",
    framework="autogen",
)
print(f"Store these — TRUST_AGENT_ID={creds['agent_id']}  TRUST_PRIVATE_KEY={creds['private_key']}")

# From then on, with those two env vars set, register_attestify_functions()
# picks them up automatically and adds attestify_trust_submit_evidence and
# attestify_trust_verify to the function map.
register_attestify_functions(
    assistant=assistant,
    executor=user_proxy,
    api_key=os.environ["ATTESTIFY_API_KEY"],
)
```

The private key is bound once when the function map is built — it's never a function argument the model supplies, so it never enters the conversation transcript.

## Getting Your API Key

Subscribe at [attestifyos.com/pricing](https://attestifyos.com/pricing) for Router access, or register free for Trust-only use at [attestifyos.com/trust](https://attestifyos.com/trust) — no card required.

## Links

- [Attestify OS](https://attestifyos.com)
- [Attestify Trust](https://attestifyos.com/trust)
- [Documentation](https://attestifyos.com/docs)
- [Get an API key](https://attestifyos.com/dashboard)
- [GitHub](https://github.com/attestifyagent/attestify-autogen)
