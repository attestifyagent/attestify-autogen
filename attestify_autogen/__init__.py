"""
attestify-autogen
=================
AutoGen function-call integration for Attestify — governed AI loop execution
with receipts, audit trails, and plan-gated enterprise features.

Quick start::

    from attestify_autogen import register_attestify_functions
    from autogen import AssistantAgent, UserProxyAgent
    import os

    assistant = AssistantAgent(name="assistant", llm_config={"config_list": [...]})
    user_proxy = UserProxyAgent(name="user", human_input_mode="NEVER", max_consecutive_auto_reply=5)

    register_attestify_functions(
        assistant=assistant,
        executor=user_proxy,
        api_key=os.environ["ATTESTIFY_API_KEY"],
    )

    user_proxy.initiate_chat(
        assistant,
        message="Summarise the latest AI governance trends and give me the receipt ID."
    )

Registered functions:

  attestify_run_loop(task, lane_id?, session_id?, max_cost_usdc?)
  attestify_get_dashboard()
  attestify_get_recent_loops(limit?)
  attestify_get_receipt(loop_id)
  attestify_get_control_tower()  [Enterprise only]

Attestify Trust — identity, signed evidence, free public verification.
No wallet, no gas, no chain. A separate concern from the functions above::

    from attestify_autogen import provision_trust_agent, register_attestify_functions

    # ONE TIME, outside any conversation:
    creds = provision_trust_agent(
        api_key=os.environ["ATTESTIFY_API_KEY"],
        display_name="AutoGen Assistant",
        framework="autogen",
    )
    # Store creds["agent_id"] / creds["private_key"] as TRUST_AGENT_ID /
    # TRUST_PRIVATE_KEY -- register_attestify_functions() picks them up
    # from those env vars automatically and adds two more functions:

  attestify_trust_submit_evidence(summary, evidence_schema?, action_basis?)
      Sign and submit evidence of real work done. Returns a signed,
      immutable, publicly verifiable receipt.

  attestify_trust_verify(receipt_id)
      Independently verify any Trust receipt by ID. Public, no API key.
"""

from __future__ import annotations

from .functions import register_attestify_functions, make_attestify_function_map
from ._trust import provision_trust_agent, generate_trust_keypair

__version__ = "0.2.0"

__all__ = [
    "register_attestify_functions", "make_attestify_function_map",
    "provision_trust_agent", "generate_trust_keypair",
]
