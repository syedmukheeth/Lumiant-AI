"""Scenario harness (docs/SCENARIO_CATALOGUE.md): every file in evals/scenarios/ is a list of scenarios with input
records, the configured rules and the expected results. Each check runs one engine capability over the shared data.
A scenario counts as supported only when its checks pass here."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from lumiant.planning import builder
from lumiant.planning.bom import explode
from lumiant.planning.commitment import analyse
from lumiant.planning.duplicates import find_duplicates
from lumiant.planning.model import ZERO
from lumiant.planning.mrp import MrpResult, run_mrp
from lumiant.planning.obsolescence import review
from lumiant.planning.scenario import assess
from lumiant.planning.suppliers import compare_suppliers
from lumiant.planning.transfers import transfer_options

SCENARIOS = Path(__file__).resolve().parents[2] / "evals" / "scenarios"


def _load() -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    cases = []
    for path in sorted(SCENARIOS.glob("*.yaml")):
        for sc in yaml.safe_load(path.read_text(encoding="utf-8")):
            for i, check in enumerate(sc["checks"]):
                cases.append((f"{sc['id']}#{i + 1} {sc['title'][:40]}", sc, check))
    return cases


CASES = _load()


def same(actual: Any, expected: Any, where: str) -> None:
    if expected is None:
        assert actual is None, f"{where}: expected none, got {actual!r}"
    elif isinstance(expected, bool):
        assert actual is expected, f"{where}: expected {expected}, got {actual!r}"
    elif isinstance(expected, (int, float, Decimal)) and not isinstance(expected, bool):
        assert actual is not None, f"{where}: expected {expected}, got none"
        assert Decimal(str(actual)).quantize(Decimal("0.0001")) == Decimal(str(expected)).quantize(Decimal("0.0001")), (
            f"{where}: expected {expected}, got {actual}"
        )
    elif isinstance(expected, date):
        assert actual == expected, f"{where}: expected {expected}, got {actual}"
    else:
        assert str(actual) == str(expected), f"{where}: expected {expected!r}, got {actual!r}"


def _all_issue_codes(r: MrpResult) -> set[str]:
    return {i.code for i in r.issues} | {i.code for p in r.planned_orders for i in p.issues}


def check_mrp(data: Any, exp: dict[str, Any], params: dict[str, Any]) -> MrpResult:
    r = run_mrp(data, substitute=params.get("substitute", True))
    lines = {f.key: f for f in r.fulfilment(data.calendar)}
    for key, fields in (exp.get("fulfilment") or {}).items():
        assert key in lines, f"no fulfilment line {key}; have {sorted(lines)}"
        for f, v in fields.items():
            if f == "reasons_contain":
                joined = " | ".join(lines[key].reasons)
                assert v in joined, f"{key} reasons {joined!r} lack {v!r}"
            else:
                same(getattr(lines[key], f), v, f"fulfilment {key}.{f}")
    for item_id, fields in (exp.get("planned") or {}).items():
        wh = fields.get("wh")
        orders = [p for p in r.planned_orders if p.item_id == str(item_id) and (wh is None or p.warehouse_id == wh)]
        assert orders, f"no planned order for {item_id}; planned: {[(p.item_id, p.quantity) for p in r.planned_orders]}"
        orders.sort(key=lambda p: (p.need, p.id))
        for f, v in fields.items():
            if f == "wh":
                continue
            if f == "qty":
                same(sum((p.quantity for p in orders), ZERO), v, f"planned {item_id}.qty")
            elif f == "net":
                same(sum((p.net for p in orders), ZERO), v, f"planned {item_id}.net")
            elif f == "count":
                same(len(orders), v, f"planned {item_id}.count")
            else:
                same(getattr(orders[0], f), v, f"planned {item_id}.{f}")
    for item_id in exp.get("no_planned", []):
        assert not [p for p in r.planned_orders if p.item_id == str(item_id)], f"{item_id} should not be planned"
    for item_id, qty in (exp.get("gross") or {}).items():
        same(sum((p.gross for (i, _w), p in r.positions.items() if i == str(item_id)), ZERO), qty, f"gross {item_id}")
    for item_id, qty in (exp.get("usable") or {}).items():
        same(sum((p.usable for (i, _w), p in r.positions.items() if i == str(item_id)), ZERO), qty, f"usable {item_id}")
    for item_id, statuses in (exp.get("not_usable") or {}).items():
        pos = [p for (i, _w), p in r.positions.items() if i == str(item_id)]
        for status, qty in statuses.items():
            same(sum((p.not_usable.get(status, ZERO) for p in pos), ZERO), qty, f"not usable {item_id}.{status}")
    for item_id, qty in (exp.get("excess") or {}).items():
        same(sum((q for i, _w, _s, _ref, q in r.excess_supply() if i == str(item_id)), ZERO), qty, f"excess {item_id}")
    for item_id, qty in (exp.get("alternate_used") or {}).items():
        used = sum(
            (
                c.used_quantity or ZERO
                for e in r.entries
                for c in e.coverage
                if c.source == "alternate" and c.item_id == str(item_id)
            ),
            ZERO,
        )
        same(used, qty, f"alternate {item_id} used")
    codes = _all_issue_codes(r)
    for code in exp.get("issues", []):
        assert code in codes, f"expected issue {code}; got {sorted(codes)}"
    for code in exp.get("absent_issues", []):
        assert code not in codes, f"unexpected issue {code}"
    return r


def run_check(sc: dict[str, Any], check: dict[str, Any]) -> None:
    raw = {**sc.get("data", {}), "today": sc["today"]}
    data = builder.planning_data(raw)
    exp = check.get("expect", {})
    kind = check["run"]
    params = check.get("params", {})
    if kind == "mrp":
        check_mrp(data, exp, params)
    elif kind == "bom":
        ex = explode(str(params["item"]), Decimal(str(params["qty"])), builder.day(params.get("date")) or data.today,
                     data.boms, data.items, data.conversions, single_level=params.get("single_level", False))  # fmt: skip
        totals = ex.totals()
        for comp, qty in (exp.get("totals") or {}).items():
            same(totals.get(str(comp)), qty, f"total {comp}")
        if "components" in exp:
            assert sorted(totals) == sorted(map(str, exp["components"])), f"components {sorted(totals)}"
        if "revision" in exp:
            same(
                {ln.revision for ln in ex.lines if ln.level == 1}.pop() if ex.lines else None,
                exp["revision"],
                "revision",
            )
        codes = {i.code for i in ex.issues}
        for code in exp.get("issues", []):
            assert code in codes, f"expected issue {code}; got {sorted(codes)}"
        if exp.get("no_issues"):
            assert not ex.issues, [i.message for i in ex.issues]
    elif kind == "suppliers":
        s = sc.get("data", {})
        cmp = compare_suppliers(
            str(params["item"]),
            Decimal(str(params["qty"])),
            today=data.today,
            need_date=builder.day(params.get("need_date")),
            offers=builder.offers(s.get("offers", [])),
            suppliers=builder.suppliers(s.get("suppliers", [])),
            deliveries=builder.deliveries(s.get("deliveries", [])),
            prices=builder.prices(s.get("price_history", [])),
            fx=builder.fx(s.get("fx", [])),
            policy=builder.supplier_policy(params.get("policy")),
            calendar=data.calendar,
            receiving_days=int(params.get("receiving_days", 0)),
            inspection_days=int(params.get("inspection_days", 0)),
        )
        by = {o.supplier_id: o for o in cmp.offers}
        if "best" in exp:
            same(cmp.best.supplier_id if cmp.best else None, exp["best"], "best supplier")
        if "ranking" in exp:
            assert [o.supplier_id for o in cmp.offers if o.eligible] == [str(x) for x in exp["ranking"]], [
                (o.supplier_id, o.eligible, o.score, o.reasons) for o in cmp.offers
            ]
        for sid, text in (exp.get("ineligible") or {}).items():
            o = by[str(sid)]
            assert not o.eligible, f"{sid} should be ineligible"
            assert text in " | ".join(o.reasons), f"{sid} reasons {o.reasons} lack {text!r}"
        for sid in exp.get("eligible", []):
            assert by[str(sid)].eligible, f"{sid} should be eligible: {by[str(sid)].reasons}"
        for sid, fields in (exp.get("offers") or {}).items():
            for f, v in fields.items():
                same(getattr(by[str(sid)], f), v, f"offer {sid}.{f}")
        for sid, text in (exp.get("notes_contain") or {}).items():
            assert text in " | ".join(by[str(sid)].notes), f"{sid} notes {by[str(sid)].notes} lack {text!r}"
        for sid, qty in (exp.get("split") or {}).items():
            got = {o.supplier_id: o.allocated for o in cmp.split}
            same(got.get(str(sid)), qty, f"split {sid}")
        if "gaps_contain" in exp:
            assert exp["gaps_contain"] in " | ".join(cmp.gaps), cmp.gaps
        if "recommendation_contains" in exp:
            assert exp["recommendation_contains"] in cmp.recommendation, cmp.recommendation
    elif kind == "duplicates":
        found = {
            f"{f.item_a}|{f.item_b}": f.verdict
            for f in find_duplicates(list(data.items.values()), include_different=True)
        }
        for pair, verdict in (exp.get("findings") or {}).items():
            same(found.get(pair), verdict, f"pair {pair}")
        for pair in exp.get("none", []):
            assert pair not in found, f"{pair} should not be flagged: {found.get(pair)}"
    elif kind == "obsolescence":
        mrp = run_mrp(data) if data.demand else None
        on_hand: dict[str, Decimal] = {}
        for s in data.stock:
            on_hand[s.item_id] = on_hand.get(s.item_id, ZERO) + s.quantity
        moves = {str(k): builder.day(v) for k, v in (sc.get("data", {}).get("last_movement") or {}).items()}
        findings = {f.item_id: f for f in review(data.items, on_hand, moves, today=data.today, boms=data.boms, mrp=mrp,
                                                  dormant_days=int(params.get("dormant_days", 365)))}  # fmt: skip
        for item_id, verdict in (exp.get("verdicts") or {}).items():
            assert str(item_id) in findings, f"no finding for {item_id}"
            same(findings[str(item_id)].verdict, verdict, f"verdict {item_id}")
        for item_id, qty in (exp.get("possible_excess") or {}).items():
            same(findings[str(item_id)].possible_excess, qty, f"excess {item_id}")
    elif kind == "transfers":
        r = run_mrp(data)
        opts = transfer_options(r, str(params["item"]), str(params["destination"]), Decimal(str(params["shortage"])),
                                builder.lanes(sc.get("data", {}).get("lanes", [])), data.calendar)  # fmt: skip
        got = [(o.source, o.quantity, o.arrival, o.cost) for o in opts if o.quantity > 0]
        want = exp.get("options", [])
        assert len(got) == len(want), f"options {got}"
        for g, w in zip(got, want, strict=True):
            same(g[0], w["source"], "transfer source")
            same(g[1], w["qty"], "transfer qty")
            if "arrival" in w:
                same(g[2], w["arrival"], "transfer arrival")
            if "cost" in w:
                same(g[3], w["cost"], "transfer cost")
    elif kind == "commitment":
        s = sc.get("data", {})
        a = analyse(
            data,
            str(params["order"]),
            offers=builder.offers(s.get("offers", [])),
            suppliers=builder.suppliers(s.get("suppliers", [])),
            deliveries=builder.deliveries(s.get("deliveries", [])),
            prices=builder.prices(s.get("price_history", [])),
            fx=builder.fx(s.get("fx", [])),
        )
        assert a is not None, "order not found"
        rec = next((o for o in a.options if o.recommended), None)

        def opt(key: str) -> Any:
            if key == "split":
                return next(o for o in a.options if o.kind == "split")
            return next(o for o in a.options if o.kind == "supplier" and o.suppliers == [key])

        for f in ("at_risk", "feasible", "recommended_delivery"):
            if f in exp:
                same(getattr(a, f), exp[f], f)
        if "recommended" in exp:
            same(
                rec.suppliers[0] if rec and rec.kind == "supplier" else (None if rec is None else "split"),
                exp["recommended"],
                "recommended",
            )
        if "recommended_kind" in exp:
            same(rec.kind if rec else None, exp["recommended_kind"], "recommended kind")
        if "option_count" in exp:
            same(len(a.options), exp["option_count"], "option count")
        for key, fields in (exp.get("options") or {}).items():
            o = opt(str(key))
            for f, v in fields.items():
                same(getattr(o, f), v, f"option {key}.{f}")
        for key, text in (exp.get("reasons_contain") or {}).items():
            assert text in " | ".join(opt(str(key)).reasons), opt(str(key)).reasons
        for f, v in (exp.get("exposure") or {}).items():
            same(getattr(a.exposure, f), v, f"exposure.{f}")
        if "explanation_contains" in exp:
            assert exp["explanation_contains"] in " | ".join(a.explanation), a.explanation
        for text in exp.get("fallbacks_contain", []):
            assert text in " | ".join(a.fallbacks), a.fallbacks
    elif kind == "assess":
        a = assess(params["question"], params.get("available", {}))
        same(a.mode, exp["mode"], "assessment mode")
        for cap in exp.get("capabilities", []):
            assert cap in a.capabilities, f"{cap} not in {a.capabilities}"
        for key in exp.get("missing", []):
            assert any(key in v for v in a.missing.values()), f"{key} not missing: {a.missing}"
        if exp.get("gaps"):
            assert a.capability_gaps, "expected capability gaps"
    else:
        raise AssertionError(f"unknown check type {kind}")


@pytest.mark.parametrize(("name", "scenario", "check"), CASES, ids=[c[0] for c in CASES])
def test_scenario(name: str, scenario: dict[str, Any], check: dict[str, Any]) -> None:
    run_check(scenario, check)
