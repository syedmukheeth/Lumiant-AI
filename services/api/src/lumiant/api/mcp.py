"""MCP server (V3, docs/05-plan/PRODUCT_V3_PLAN.md §4): a customer's own AI assistant (Claude, ChatGPT, Microsoft
Copilot, Gemini, any Model Context Protocol client) asks Lumiant inventory questions through the same typed tools the
Analyst uses.

- Streamable HTTP transport, JSON responses: `POST /mcp` with one JSON-RPC 2.0 message; no server-initiated stream.
- Authentication: an API key (`Authorization: Bearer lmk_...`), so the assistant acts with that key's permissions and
  warehouse scope. Every call is audited.
- ADR-0002 holds: the assistant chooses a tool and its typed arguments; the platform runs validated plans and returns
  exact figures with provenance. The assistant never sends SQL and never computes the numbers.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response

from lumiant.agent.providers import ToolCall
from lumiant.agent.tools import TOOLS, ToolContext
from lumiant.auth.deps import current_principal, get_container, rate_limit
from lumiant.auth.principal import Principal
from lumiant.container import Container

router = APIRouter(tags=["mcp"])
SUPPORTED_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER_INFO = {"name": "lumiant", "title": "Lumiant inventory intelligence", "version": "0.3.0"}
INSTRUCTIONS = (
    "Lumiant answers questions about inventory: stock, value, risks, planning and suppliers. Pick the tool that fits "
    "and pass its typed arguments. Every figure comes from the customer's data through validated queries with "
    "provenance; quote figures exactly as returned and say when a result is partial or the data is stale. "
    "Use ask_lumiant for a question in plain language when no single tool fits."
)
ASK_TOOL = {
    "name": "ask_lumiant",
    "title": "Ask Lumiant",
    "description": "Ask an inventory question in plain language. Lumiant picks the analyses, runs them and answers "
    "with exact figures and their sources.",
    "inputSchema": {
        "type": "object",
        "properties": {"question": {"type": "string", "minLength": 2, "maxLength": 2000}},
        "required": ["question"],
        "additionalProperties": False,
    },
    "annotations": {"readOnlyHint": True, "openWorldHint": False},
}


def _rpc_result(msg_id: Any, result: dict[str, Any]) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": msg_id, "result": jsonable_encoder(result)})


def _rpc_error(msg_id: Any, code: int, message: str) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}})


def _tools_for(principal: Principal) -> list[dict[str, Any]]:
    tools = [
        {
            "name": t.name,
            "title": t.name.replace("_", " ").capitalize(),
            "description": t.description,
            "inputSchema": t.args.model_json_schema(),
            "annotations": {"readOnlyHint": True, "openWorldHint": False},
        }
        for t in TOOLS.values()
        if all(principal.has(p) for p in t.permissions)
    ]
    return [*tools, ASK_TOOL]


def _text(answer: str, blocks: list[Any], warnings: list[dict[str, str]]) -> str:
    """A readable answer for clients that show only text: the answer, the first rows of each table, the warnings."""
    lines = [answer]
    for block in blocks:
        b = block if isinstance(block, dict) else getattr(block, "__dict__", {})
        rows = b.get("rows") or []
        cols = b.get("columns") or []
        if rows and cols:
            keys = [c.get("key") for c in cols if isinstance(c, dict)]
            labels = [c.get("label", c.get("key")) for c in cols if isinstance(c, dict)]
            lines.append("")
            lines.append(" | ".join(str(x) for x in labels))
            lines += [" | ".join(str(r.get(k, "")) for k in keys) for r in rows[:15]]
            if len(rows) > 15:
                lines.append(f"... {len(rows) - 15} more rows")
    lines += [f"Note: {w.get('message')}" for w in warnings if w.get("message")]
    return "\n".join(lines)


def _call(container: Container, principal: Principal, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == ASK_TOOL["name"]:
        question = arguments.get("question")
        if not isinstance(question, str) or not 2 <= len(question) <= 2000:
            return {"content": [{"type": "text", "text": "Pass a question of 2 to 2000 characters."}], "isError": True}
        out = container.agent.chat(principal, question)
        structured = {k: out.get(k) for k in ("answer", "blocks", "provenance", "warnings", "tool_calls")}
        text = _text(out.get("answer", ""), out.get("blocks") or [], out.get("warnings") or [])
        return {"content": [{"type": "text", "text": text}], "structuredContent": structured, "isError": False}
    ctx = ToolContext(container.query, principal)
    output = container.agent._run_tool(ctx, ToolCall(name, arguments))
    structured = {
        "answer": output.answer,
        "blocks": output.blocks,
        "provenance": output.provenance,
        "warnings": output.warnings,
    }
    return {
        "content": [{"type": "text", "text": _text(output.answer, list(output.blocks), output.warnings)}],
        "structuredContent": structured,
        "isError": not output.ok,
    }


@router.get("/mcp")
def mcp_stream() -> Response:
    """No server-initiated stream: every answer comes back on its POST."""
    return Response(status_code=405, headers={"Allow": "POST"})


@router.post("/mcp", dependencies=[Depends(rate_limit("query"))])
async def mcp(
    request: Request,
    principal: Annotated[Principal, Depends(current_principal)],
    container: Annotated[Container, Depends(get_container)],
) -> Response:
    try:
        msg = await request.json()
    except ValueError:
        return _rpc_error(None, -32700, "Parse error")
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return _rpc_error(None, -32600, "Invalid request: send one JSON-RPC 2.0 message")
    method, msg_id, params = msg["method"], msg.get("id"), msg.get("params") or {}
    if msg_id is None:  # a notification (e.g. notifications/initialized): accepted, nothing to answer
        return Response(status_code=202)
    if method == "initialize":
        asked = params.get("protocolVersion")
        version = asked if asked in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
        return _rpc_result(
            msg_id,
            {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
                "instructions": INSTRUCTIONS,
            },
        )
    if method == "ping":
        return _rpc_result(msg_id, {})
    if method == "tools/list":
        return _rpc_result(msg_id, {"tools": _tools_for(principal)})
    if method == "tools/call":
        name, arguments = params.get("name"), params.get("arguments") or {}
        if not isinstance(name, str) or not isinstance(arguments, dict):
            return _rpc_error(msg_id, -32602, "Invalid params: name and arguments are required")
        visible = {t["name"] for t in _tools_for(principal)}
        if name not in visible:
            # Same answer for unknown and not permitted: a client learns nothing about hidden tools.
            return _rpc_error(msg_id, -32602, f"Unknown tool: {name}")
        result = _call(container, principal, name, arguments)
        container.query.record(principal, f"mcp:{name}", None, "allow", "error" if result["isError"] else "ok")
        return _rpc_result(msg_id, result)
    return _rpc_error(msg_id, -32601, f"Method not found: {method}")
