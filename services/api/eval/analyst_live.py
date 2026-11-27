"""Live Analyst eval (S11): ask the real external provider the questions in `evals/live.yaml` on synthetic tenants.

    LUMIANT_AGENT_PROVIDER=gemini LUMIANT_GEMINI_API_KEY=... uv run python eval/analyst_live.py [--limit N]

Runs `AgentService` in-process (no server), signs in as the synthetic dev users, and scores each answer:
  tools     at least one expected tool was called (or none expected)
  grounded  the grounding check passed (no untraced figure reached the user)
  worded    the model's own wording was used, not the template fallback (answers only)
  honest    a decline case said the data cannot answer and showed no figures the tools did not return
Writes a Markdown report to docs/logs/live-eval/<date>.md (summary and one line per case; no answer text with
figures beyond what the synthetic tenants hold). Refuses to run without a key, against non-synthetic tenants, or
when the provider is not external. Every call spends the tenant's daily AI allowance like any other question.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime
from typing import Any

import yaml

from lumiant.agent.service import AgentService
from lumiant.core.config import BASE_DIR, Settings
from lumiant.main import build_container

CASES = BASE_DIR / "evals" / "live.yaml"
REPORT_DIR = BASE_DIR.parents[1] / "docs" / "logs" / "live-eval"
DECLINE_WORDS = ("not in your data", "can't", "cannot", "not available", "isn't", "is not", "no ", "not ")


def score(case: dict[str, Any], out: dict[str, Any]) -> dict[str, Any]:
    used = [c["name"] for c in out["tool_calls"]]
    expected = case.get("tools") or []
    tools_ok = not expected or any(t in used for t in expected)  # no expectation: any tool (or none) is fine
    grounded = bool(out["grounding"]["passed"])
    worded = out["grounding"].get("source") == "model"
    text = (out["answer"] or "").lower()
    honest = True
    if case["expect"] == "decline":
        honest = out["kind"] in ("unsupported", "clarify") or any(w in text for w in DECLINE_WORDS)
    passed = tools_ok and grounded and honest and (worded or case["expect"] == "decline")
    return {
        "user": case["user"],
        "question": case["question"],
        "expect": case["expect"],
        "used": used,
        "mode": out["mode"],
        "kind": out["kind"],
        "tools_ok": tools_ok,
        "grounded": grounded,
        "worded": worded,
        "honest": honest,
        "passed": passed,
        "ms": out.get("elapsed_ms"),
        "notice": out.get("notice") or "",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=0, help="run only the first N cases")
    args = parser.parse_args(argv)
    settings = Settings()
    if settings.agent_provider == "rules" or not (settings.gemini_api_key or settings.anthropic_api_key):
        print("Live eval needs LUMIANT_AGENT_PROVIDER=gemini (or anthropic) and its API key.", file=sys.stderr)
        return 2
    container = build_container(settings)
    if container.dev_auth is None:
        print("Live eval signs in as the synthetic dev users: run with development authentication.", file=sys.stderr)
        return 2
    agent: AgentService = container.agent
    cases = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    if args.limit:
        cases = cases[: args.limit]
    results = []
    for i, case in enumerate(cases, 1):
        _token, principal = container.dev_auth.issue(case["user"])
        if not container.tenants.get(principal.tenant_id).synthetic:
            print(f"refusing non-synthetic tenant {principal.tenant_id}", file=sys.stderr)
            return 2
        t0 = time.perf_counter()
        try:
            out = agent.chat(principal, case["question"])
        except Exception as exc:  # report and keep going: one failure must not hide the rest
            results.append({**case, "used": [], "passed": False, "error": type(exc).__name__})
            continue
        r = score(case, out)
        results.append(r)
        flag = "PASS" if r["passed"] else "FAIL"
        print(f"[{i}/{len(cases)}] {flag} {round(time.perf_counter() - t0, 1)}s {case['question'][:70]}")
    passed = sum(1 for r in results if r.get("passed"))
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d-%H%M")
    model = settings.gemini_model if settings.agent_provider == "gemini" else settings.agent_model
    lines = [
        f"# Live Analyst eval · {stamp} UTC",
        "",
        f"Provider: `{settings.agent_provider}` · model: `{model}`",
        f"Result: **{passed}/{len(results)} passed** (tools, grounding, model wording, honest declines). "
        "Synthetic tenants only.",
        "",
        "| # | User | Question | Expect | Tools used | Mode | Tools | Grounded | Worded | Honest | Pass |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(results, 1):
        verdict = "yes" if r.get("passed") else "NO" + (f" ({r['error']})" if r.get("error") else "")
        lines.append(
            f"| {i} | {r['user']} | {r['question']} | {r['expect']} | {', '.join(r.get('used', [])) or '-'} | "
            f"{r.get('mode', '-')} | {r.get('tools_ok', '-')} | {r.get('grounded', '-')} | {r.get('worded', '-')} | "
            f"{r.get('honest', '-')} | {verdict} |"
        )
    report = REPORT_DIR / f"{stamp}.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{passed}/{len(results)} passed · report: {report}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
