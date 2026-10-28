"""AgentService: one bounded, audited pass from a question to a grounded answer.

`chat_events` yields progress events (understand → each tool → grounding → answer) so the browser can show the
agent's work as it happens; `chat` runs the same pass and returns only the final answer.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any

from pydantic import ValidationError

from lumiant.agent.context import MAX_HISTORY, ChatContext, HistoryTurn
from lumiant.agent.grounding import collect_numbers, ungrounded_numbers
from lumiant.agent.providers import SUGGESTIONS, Decision, Provider, RuleBasedProvider, ToolCall, build_provider
from lumiant.agent.tools import TOOLS, NarrowArgs, ToolContext, ToolOutput, visible_warehouses
from lumiant.auth.principal import Principal
from lumiant.core.config import Settings
from lumiant.core.errors import AppError
from lumiant.core.logging import request_id_var
from lumiant.query.plan import QueryPlan
from lumiant.query.service import QueryService

log = logging.getLogger("lumiant.agent")
MAX_TOOL_CALLS = 4
MAX_QUESTION_CHARS = 500
Event = dict[str, Any]

TOOL_LABELS = {
    "stock_position": "Looking up where the item is held",
    "stock_by": "Grouping stock",
    "top_value_items": "Ranking items by value",
    "below_reorder": "Checking reorder levels",
    "excess_stock": "Checking maximum stock levels",
    "dormant": "Scanning movement history",
    "expiring_lots": "Checking lot expiry dates",
    "data_quality": "Running data-quality checks",
    "cost_comparison": "Comparing costing methods",
    "special_storage": "Reading storage requirements",
    "concentration": "Computing value concentration",
    "insights": "Running every insight check",
}
# A page filter narrows a tool unless the tool groups by that same field (then the comparison is the point).
_FILTER_DIMENSION = {
    "warehouse_id": "warehouse",
    "item_group": "item_group",
    "stage": "stage",
    "stock_status": "stock_status",
}


def _label(call: ToolCall) -> str:
    label = TOOL_LABELS.get(call.name, call.name)
    if call.name == "stock_by" and call.args.get("dimension"):
        label += " by " + str(call.args["dimension"]).replace("_", " ")
    return label


def _step(step_id: str, label: str, status: str, **extra: Any) -> Event:
    return {"type": "step", "id": step_id, "label": label, "status": status, **extra}


class AgentService:
    def __init__(self, query: QueryService, settings: Settings) -> None:
        self.query = query
        self.settings = settings

    def _provider(self, principal: Principal) -> tuple[Provider, str | None]:
        tenant = self.query.tenants.get(principal.tenant_id)
        s = self.settings
        secret, model = (
            (s.gemini_api_key, s.gemini_model) if s.agent_provider == "gemini" else (s.anthropic_api_key, s.agent_model)
        )
        return build_provider(
            configured=s.agent_provider,
            api_key=secret.get_secret_value() if secret else None,
            model=model,
            tenant_approved=tenant.ai.external_provider_approved,
        )

    def _run_tool(self, ctx: ToolContext, call: ToolCall) -> ToolOutput:
        tool = TOOLS.get(call.name)
        if tool is None or not all(ctx.principal.has(p) for p in tool.permissions):
            # Same message for "unknown" and "not allowed": the model/user learns nothing about hidden tools.
            return ToolOutput(call.name, call.name, "That analysis is not available to your role.", ok=False)
        try:
            args = tool.args.model_validate(call.args)
        except ValidationError:
            return ToolOutput(
                call.name, call.name, "I could not use those arguments safely, so I did not run the analysis.", ok=False
            )
        try:
            return tool.run(ctx, args)
        except AppError as exc:
            return ToolOutput(
                call.name, call.name, exc.message, warnings=[{"code": exc.code, "message": exc.message}], ok=False
            )

    # ------------------------------------------------------------------------------------ screen context
    def _check_context(self, ctx: ToolContext) -> Decision | None:
        """Selected/filtered warehouses must be visible to the principal and selected items must exist."""
        c = ctx.context
        if c is None:
            return None
        warehouses = [s.id for s in c.selections if s.kind == "warehouse"]
        if c.filters.warehouse_id:
            warehouses.append(c.filters.warehouse_id)
        if warehouses:
            visible = {str(w["warehouse_id"]) for w in visible_warehouses(ctx)}
            if any(w not in visible for w in warehouses):
                self.query.record(
                    ctx.principal, "agent:context", "warehouse", "deny", "denied", reason="forbidden_scope"
                )
                return Decision(
                    "unsupported",
                    message="That selection is outside the warehouses you can see, so I did not analyse it.",
                )
        for item_id in [s.id for s in c.selections if s.kind == "item"]:
            plan = QueryPlan.model_validate(
                {
                    "dataset": "item",
                    "dimensions": ["item_id"],
                    "filters": [{"field": "item_id", "op": "eq", "value": item_id}],
                }
            )
            if not self.query.run_plan(plan, ctx.principal, action="agent:resolve_item").rows:
                return Decision("unsupported", message="I couldn't find the selected item in the item master.")
        return None

    @staticmethod
    def _narrow(calls: list[ToolCall], ctx: ToolContext) -> list[ToolCall]:
        f = ctx.context.filters if ctx.context else None
        if f is None:
            return calls
        out = []
        for call in calls:
            tool = TOOLS.get(call.name)
            if tool is not None and issubclass(tool.args, NarrowArgs):
                args = dict(call.args)
                for key, dimension in _FILTER_DIMENSION.items():
                    value = getattr(f, key)
                    if value and args.get(key) is None and args.get("dimension") != dimension:
                        args[key] = value
                call = ToolCall(call.name, args)
            out.append(call)
        return out

    # ------------------------------------------------------------------------------------ the pass
    def chat(
        self,
        principal: Principal,
        message: str,
        context: ChatContext | None = None,
        history: list[HistoryTurn] | None = None,
    ) -> dict[str, Any]:
        final: dict[str, Any] | None = None
        for event in self.chat_events(principal, message, context, history):
            if event["type"] == "answer":
                final = event["answer"]
        assert final is not None
        return final

    def chat_events(
        self,
        principal: Principal,
        message: str,
        context: ChatContext | None = None,
        history: list[HistoryTurn] | None = None,
    ) -> Iterator[Event]:
        started = time.perf_counter()
        question = " ".join(message.split())[:MAX_QUESTION_CHARS]
        ctx = ToolContext(self.query, principal, context, list(history or [])[-MAX_HISTORY:])
        steps: list[Event] = []

        def done(event: Event) -> Event:
            steps.append(event)
            return event

        yield _step("understand", "Understanding the question", "running")
        provider, notice = self._provider(principal)
        decision: Decision
        refusal = self._check_context(ctx)
        if refusal is not None:
            provider, notice, decision = RuleBasedProvider(), None, refusal
        else:
            try:
                decision = provider.decide(question, ctx)
            except Exception as exc:
                if not provider.external:
                    raise
                log.warning("external_provider_failed", extra={"error_type": type(exc).__name__})
                provider, notice = (
                    RuleBasedProvider(),
                    "The external AI provider is unavailable; using built-in question matching.",
                )
                decision = provider.decide(question, ctx)
        calls = self._narrow(decision.calls[:MAX_TOOL_CALLS], ctx) if decision.kind == "tools" else []
        plan_detail = ", ".join(_label(c).lower() for c in calls) if calls else decision.kind
        yield done(_step("understand", "Understanding the question", "done", detail=plan_detail, mode=provider.name))

        outputs: list[ToolOutput] = []
        for i, call in enumerate(calls):
            step_id, label = f"tool:{i}", _label(call)
            yield _step(step_id, label, "running", tool=call.name)
            t0 = time.perf_counter()
            out = self._run_tool(ctx, call)
            outputs.append(out)
            rows = sum(len(b.get("rows", [])) for b in out.blocks)
            ms = round((time.perf_counter() - t0) * 1000)
            yield done(_step(step_id, label, "done" if out.ok else "failed", tool=call.name, rows=rows, ms=ms))
            for block in out.blocks:
                yield {"type": "block", "step": step_id, "block": block}

        evidence = collect_numbers(question)
        for out in outputs:
            collect_numbers(out.data, evidence)
            for block in out.blocks:
                evidence.add(str(len(block.get("rows", []))))
        template = "\n\n".join(o.answer for o in outputs) if outputs else decision.message
        answer, grounding = template, {"passed": True, "ungrounded": [], "source": "template"}
        if outputs and provider.external and all(o.ok for o in outputs):
            yield _step("compose", "Writing the answer", "running")
            try:
                prose = provider.compose(question, outputs, ctx)
            except Exception as exc:
                log.warning("external_compose_failed", extra={"error_type": type(exc).__name__})
                prose = None
            if prose:
                bad = ungrounded_numbers(prose, evidence)
                if bad:
                    grounding = {
                        "passed": True,
                        "ungrounded": bad,
                        "source": "template",
                        "note": "AI wording rejected: it contained numbers not in the results.",
                    }
                else:
                    answer, grounding = prose, {"passed": True, "ungrounded": [], "source": "model"}
            yield done(_step("compose", "Writing the answer", "done"))
        bad_template = ungrounded_numbers(answer, evidence)
        if bad_template:  # should be impossible; never ship an ungrounded number
            log.error("template_ungrounded", extra={"count": len(bad_template)})
            grounding = {"passed": False, "ungrounded": bad_template, "source": grounding["source"]}
        if outputs:
            verdict = "every number traced to the results" if grounding["passed"] else "ungrounded numbers found"
            yield done(_step("ground", "Checking every number against the results", "done", detail=verdict))

        sent_rows = getattr(provider, "sent_rows", 0)
        self.query.record(
            principal,
            "agent:chat",
            None,
            "allow",
            "ok",
            fields=tuple(c.name for c in calls),
            rows=sum(len(b.get("rows", [])) for o in outputs for b in o.blocks),
            reason=f"{provider.name}:{decision.kind}" + (":context" if context and context.selections else ""),
        )
        if provider.external:
            self.query.record(
                principal,
                "agent:disclosure",
                None,
                "allow",
                "ok",
                fields=("question", "tool_results"),
                rows=sent_rows,
                reason=provider.name,
            )

        follow = list(dict.fromkeys(f for o in outputs for f in o.follow_ups))
        if decision.kind == "unsupported" and not outputs:
            follow = SUGGESTIONS[:5]
        warnings = [w for o in outputs for w in o.warnings]
        yield {
            "type": "answer",
            "answer": {
                "mode": provider.name,
                "notice": notice,
                "kind": decision.kind,
                "answer": answer,
                "blocks": [b for o in outputs for b in o.blocks],
                "tool_calls": [{"name": c.name, "args": c.args} for c in calls],
                "provenance": [o.provenance for o in outputs if o.provenance],
                "warnings": warnings,
                "follow_ups": follow,
                "choices": decision.choices,
                "grounding": grounding,
                "steps": steps,
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
                "request_id": request_id_var.get(),
            },
        }

    def record_feedback(self, principal: Principal, rating: str, reason: str | None) -> None:
        self.query.record(principal, "agent:feedback", None, "allow", "ok", reason=f"{rating}:{(reason or '')[:40]}")
