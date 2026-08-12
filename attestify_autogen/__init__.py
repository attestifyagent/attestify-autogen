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
"""

from __future__ import annotations

from .functions import register_attestify_functions, make_attestify_function_map

__version__ = "0.1.1"

__all__ = ["register_attestify_functions", "make_attestify_function_map"]
