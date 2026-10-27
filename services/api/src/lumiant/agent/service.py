"""AgentService: one bounded, audited pass from a question to a grounded answer."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from lumiant.agent.grounding import collect_numbers, ungrounded_numbers
from lumiant.agent.providers import SUGGESTIONS, Decision, Provider, RuleBasedProvider, ToolCall, build_provider
from lumiant.agent.tools import TOOLS, ToolContext, ToolOutput
from lumiant.auth.principal import Principal
from lumiant.core.config import Settings
from lumiant.core.errors import AppError
from lumiant.core.logging import request_id_var
from lumiant.query.service import QueryService

log = logging.getLogger("lumiant.agent")
MAX_TOOL_CALLS = 4
MAX_QUESTION_CHARS = 500


class AgentService:
    def __init__(self, query: QueryService, settings: Settings) -> None:
        self.query = query
        self.settings = settings

    def _provider(self, principal: Principal) -> tuple[Provider, str | None]:
        tenant = self.query.tenants.get(principal.tenant_id)
        key = self.settings.anthropic_api_key.get_secret_value() if self.settings.anthropic_api_key else None
        return build_provider(
            configured=self.settings.agent_provider,
            api_key=key,
            model=self.settings.agent_model,
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

    def chat(self, principal: Principal, message: str) -> dict[str, Any]:
        question = " ".join(message.split())[:MAX_QUESTION_CHARS]
        ctx = ToolContext(self.query, principal)
        provider, notice = self._provider(principal)
        decision: Decision
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

        outputs: list[ToolOutput] = []
        calls = decision.calls[:MAX_TOOL_CALLS] if decision.kind == "tools" else []
        for call in calls:
            outputs.append(self._run_tool(ctx, call))

        evidence = collect_numbers(question)
        for out in outputs:
            collect_numbers(out.data, evidence)
            for block in out.blocks:
                evidence.add(str(len(block.get("rows", []))))
        template = "\n\n".join(o.answer for o in outputs) if outputs else decision.message
        answer, grounding = template, {"passed": True, "ungrounded": [], "source": "template"}
        if outputs and provider.external and all(o.ok for o in outputs):
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
        bad_template = ungrounded_numbers(answer, evidence)
        if bad_template:  # should be impossible; never ship an ungrounded number
            log.error("template_ungrounded", extra={"count": len(bad_template)})
            grounding = {"passed": False, "ungrounded": bad_template, "source": grounding["source"]}

        sent_rows = getattr(provider, "sent_rows", 0)
        self.query.record(
            principal,
            "agent:chat",
            None,
            "allow",
            "ok",
            fields=tuple(c.name for c in calls),
            rows=sum(len(b.get("rows", [])) for o in outputs for b in o.blocks),
            reason=f"{provider.name}:{decision.kind}",
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
        return {
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
            "request_id": request_id_var.get(),
        }

    def record_feedback(self, principal: Principal, rating: str, reason: str | None) -> None:
        self.query.record(principal, "agent:feedback", None, "allow", "ok", reason=f"{rating}:{(reason or '')[:40]}")
