"""
AutoGen function-call integration for Attestify.

``register_attestify_functions`` wires Attestify API calls as AutoGen
function_map entries and injects the corresponding OpenAI function schemas
into the assistant's llm_config, so the model can call them natively.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ._http import _Client, AttestifyError, AttestifyPermissionError, DEFAULT_BASE_URL, DEFAULT_TIMEOUT, DEFAULT_RETRIES


def _safe(val: Any) -> str:
    if isinstance(val, str): return val
    try: return json.dumps(val, default=str)
    except Exception: return str(val)


def make_attestify_function_map(
    api_key:     str,
    base_url:    str   = DEFAULT_BASE_URL,
    timeout_s:   float = DEFAULT_TIMEOUT,
    max_retries: int   = DEFAULT_RETRIES,
    include_control_tower: bool = True,
) -> Dict[str, Any]:
    """
    Return a ``function_map`` dict suitable for AutoGen's ``UserProxyAgent``.

    Example::

        user_proxy = UserProxyAgent(
            name="user",
            function_map=make_attestify_function_map(api_key=key),
        )
    """
    client = _Client(api_key=api_key, base_url=base_url, timeout_s=timeout_s, max_retries=max_retries)

    def attestify_run_loop(task: str, lane_id: str = "", session_id: str = "", max_cost_usdc: float = 0.0) -> str:
        payload: dict = {"intent": task}
        if lane_id:       payload["lane_id"]     = lane_id
        if session_id:    payload["session_id"]  = session_id
        if max_cost_usdc: payload["constraints"] = {"max_cost_usdc": max_cost_usdc}
        try:    return _safe(client.post("/api/run", payload))
        except AttestifyError as e: return json.dumps({"error": str(e), "status": e.status})

    def attestify_get_dashboard() -> str:
        try:    return _safe(client.get("/api/dashboard"))
        except AttestifyError as e: return json.dumps({"error": str(e), "status": e.status})

    def attestify_get_recent_loops(limit: int = 25) -> str:
        # /api/dashboard returns the tenant-scoped receipt history for the
        # caller's own API key. There is no separate per-tenant "list loops"
        # endpoint, so we reuse it and trim to `limit`.
        try:
            result = client.get("/api/dashboard")
            receipts = result.get("receipts", []) if isinstance(result, dict) else []
            return _safe({"loops": receipts[:max(1, min(limit, 100))]})
        except AttestifyError as e: return json.dumps({"error": str(e), "status": e.status})

    def attestify_get_receipt(loop_id: str) -> str:
        if not loop_id: return json.dumps({"error": "loop_id is required"})
        try:    return _safe(client.get(f"/api/receipts/{loop_id}"))
        except AttestifyError as e: return json.dumps({"error": str(e), "status": e.status})

    fmap = {
        "attestify_run_loop":          attestify_run_loop,
        "attestify_get_dashboard":     attestify_get_dashboard,
        "attestify_get_recent_loops":  attestify_get_recent_loops,
        "attestify_get_receipt":       attestify_get_receipt,
    }

    if include_control_tower:
        def attestify_get_control_tower() -> str:
            try:    return _safe(client.get("/api/control-tower"))
            except AttestifyPermissionError: return json.dumps({"error": "Enterprise plan required.", "status": 403})
            except AttestifyError as e: return json.dumps({"error": str(e), "status": e.status})
        fmap["attestify_get_control_tower"] = attestify_get_control_tower

    return fmap


def register_attestify_functions(
    assistant: Any,
    executor:  Any,
    api_key:   str,
    base_url:  str   = DEFAULT_BASE_URL,
    timeout_s: float = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_RETRIES,
    include_control_tower: bool = True,
) -> None:
    """
    Register Attestify functions on an AutoGen AssistantAgent + executor pair.

    Injects the function schemas into ``assistant.llm_config["functions"]``
    and sets ``executor.function_map`` so the executor can call them.

    Args:
        assistant: An ``autogen.AssistantAgent`` instance.
        executor:  An ``autogen.UserProxyAgent`` or similar executor.
        api_key:   Attestify API key.
    """
    fmap = make_attestify_function_map(
        api_key=api_key, base_url=base_url,
        timeout_s=timeout_s, max_retries=max_retries,
        include_control_tower=include_control_tower,
    )

    schemas: List[dict] = [
        {
            "name": "attestify_run_loop",
            "description": "Submit a task to the Attestify loop router for governed execution. Returns loop_id, status, cost_usdc, output, and receipt_url.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task":          {"type": "string",  "description": "Natural-language task or intent."},
                    "lane_id":       {"type": "string",  "description": "Optional specific lane to invoke."},
                    "session_id":    {"type": "string",  "description": "Optional memory continuity ID."},
                    "max_cost_usdc": {"type": "number",  "description": "Optional spend cap in USDC. 0 = no cap."},
                },
                "required": ["task"],
            },
        },
        {
            "name": "attestify_get_dashboard",
            "description": "Fetch the tenant's run count, quota, plan tier, and recent receipts.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "attestify_get_recent_loops",
            "description": "List the most recent loop receipts for this tenant.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "Max receipts to return (1-100)."}},
                "required": [],
            },
        },
        {
            "name": "attestify_get_receipt",
            "description": "Retrieve a single verified loop receipt by its loop_id.",
            "parameters": {
                "type": "object",
                "properties": {"loop_id": {"type": "string", "description": "The loop_id to retrieve."}},
                "required": ["loop_id"],
            },
        },
    ]

    if include_control_tower:
        schemas.append({
            "name": "attestify_get_control_tower",
            "description": "Enterprise-only: live governance data and cross-tenant run visibility.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        })

    if not hasattr(assistant, "llm_config") or not isinstance(assistant.llm_config, dict):
        raise ValueError("assistant.llm_config must be a dict")

    assistant.llm_config.setdefault("functions", []).extend(schemas)
    executor.function_map = {**getattr(executor, "function_map", {}), **fmap}
