"""
AutoGen function-call integration for Attestify.

``register_attestify_functions`` wires Attestify API calls as AutoGen
function_map entries and injects the corresponding OpenAI function schemas
into the assistant's llm_config, so the model can call them natively.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from ._http import _Client, AttestifyError, AttestifyPermissionError, DEFAULT_BASE_URL, DEFAULT_TIMEOUT, DEFAULT_RETRIES
from ._trust import sign_trust_evidence


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
    trust_agent_id:    Optional[str] = None,
    trust_private_key: Optional[str] = None,
    include_trust: bool = True,
) -> Dict[str, Any]:
    """
    Return a ``function_map`` dict suitable for AutoGen's ``UserProxyAgent``.

    trust_agent_id/trust_private_key (or the TRUST_AGENT_ID/TRUST_PRIVATE_KEY
    env vars) enable two Trust functions -- attestify_trust_submit_evidence
    and attestify_trust_verify -- Attestify's no-wallet agent identity and
    signed-evidence layer, a separate concern from the Router functions
    below. Provision the agent/key once via provision_trust_agent(), never
    inside a running conversation.

    Example::

        user_proxy = UserProxyAgent(
            name="user",
            function_map=make_attestify_function_map(api_key=key),
        )
    """
    client = _Client(api_key=api_key, base_url=base_url, timeout_s=timeout_s, max_retries=max_retries)
    resolved_trust_agent_id = trust_agent_id or os.environ.get("TRUST_AGENT_ID", "")
    resolved_trust_private_key = trust_private_key or os.environ.get("TRUST_PRIVATE_KEY", "")

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

    # ── Attestify Trust ── a separate concern from Router execution above
    # (/api/trust/v1/*, no x402, no lanes, no spend). agent_id/private_key
    # are closed over here, at function_map-build time -- never a function
    # parameter the model supplies, so the private key never appears in the
    # conversation transcript.
    if include_trust and resolved_trust_agent_id and resolved_trust_private_key:
        def attestify_trust_submit_evidence(summary: str, evidence_schema: str = "work-completion/v1", action_basis: str = "explicit") -> str:
            try:
                signed = sign_trust_evidence(
                    agent_id=resolved_trust_agent_id, schema=evidence_schema,
                    payload={"summary": summary}, private_key=resolved_trust_private_key,
                    action_basis=action_basis,
                )
                receipt = client.post("/api/trust/v1/evidence", signed)
                r = receipt.get("receipt", receipt)
                return _safe({
                    "receipt_id": r.get("id"),
                    "assurance_level": r.get("assurance_level"),
                    "issued_at": r.get("issued_at"),
                    "verify_url": f"https://attestifyos.com/trust/verify?receipt={r.get('id')}",
                })
            except AttestifyError as e:
                return json.dumps({"error": str(e), "status": e.status})
        fmap["attestify_trust_submit_evidence"] = attestify_trust_submit_evidence

        def attestify_trust_verify(receipt_id: str) -> str:
            if not receipt_id: return json.dumps({"error": "receipt_id is required"})
            try:    return _safe(client.get_public(f"/api/trust/v1/verify/{receipt_id}"))
            except AttestifyError as e: return json.dumps({"error": str(e), "status": e.status})
        fmap["attestify_trust_verify"] = attestify_trust_verify

    return fmap


def register_attestify_functions(
    assistant: Any,
    executor:  Any,
    api_key:   str,
    base_url:  str   = DEFAULT_BASE_URL,
    timeout_s: float = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_RETRIES,
    include_control_tower: bool = True,
    trust_agent_id:    Optional[str] = None,
    trust_private_key: Optional[str] = None,
    include_trust: bool = True,
) -> None:
    """
    Register Attestify functions on an AutoGen AssistantAgent + executor pair.

    Injects the function schemas into ``assistant.llm_config["functions"]``
    and sets ``executor.function_map`` so the executor can call them.

    Args:
        assistant: An ``autogen.AssistantAgent`` instance.
        executor:  An ``autogen.UserProxyAgent`` or similar executor.
        api_key:   Attestify API key.
        trust_agent_id:    Attestify Trust agent ID (or TRUST_AGENT_ID env
                           var) -- enables attestify_trust_submit_evidence
                           and attestify_trust_verify. Provision once via
                           provision_trust_agent(), never per-conversation.
        trust_private_key: That agent's Ed25519 private key (or
                           TRUST_PRIVATE_KEY env var).
    """
    fmap = make_attestify_function_map(
        api_key=api_key, base_url=base_url,
        timeout_s=timeout_s, max_retries=max_retries,
        include_control_tower=include_control_tower,
        trust_agent_id=trust_agent_id, trust_private_key=trust_private_key,
        include_trust=include_trust,
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

    resolved_trust_agent_id = trust_agent_id or os.environ.get("TRUST_AGENT_ID", "")
    resolved_trust_private_key = trust_private_key or os.environ.get("TRUST_PRIVATE_KEY", "")
    if include_trust and resolved_trust_agent_id and resolved_trust_private_key:
        schemas.append({
            "name": "attestify_trust_submit_evidence",
            "description": (
                "Sign and submit evidence that this agent completed real work, producing a signed, "
                "timestamped, publicly verifiable receipt -- no wallet, no gas, no chain. Call after "
                "finishing something worth a permanent record, not for every step."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Plain-language description of the work actually done. Gets signed and permanently recorded -- be specific and truthful."},
                    "evidence_schema": {"type": "string", "description": "Evidence schema version. Default 'work-completion/v1' covers the general case."},
                    "action_basis": {"type": "string", "enum": ["explicit", "discretionary"], "description": "'explicit' if asked to do this, 'discretionary' if done on the agent's own initiative."},
                },
                "required": ["summary"],
            },
        })
        schemas.append({
            "name": "attestify_trust_verify",
            "description": "Independently verify any Attestify Trust receipt by ID. Public, no API key needed.",
            "parameters": {
                "type": "object",
                "properties": {"receipt_id": {"type": "string", "description": "The receipt ID to verify."}},
                "required": ["receipt_id"],
            },
        })

    if not hasattr(assistant, "llm_config") or not isinstance(assistant.llm_config, dict):
        raise ValueError("assistant.llm_config must be a dict")

    assistant.llm_config.setdefault("functions", []).extend(schemas)
    executor.function_map = {**getattr(executor, "function_map", {}), **fmap}
