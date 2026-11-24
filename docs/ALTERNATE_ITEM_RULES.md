# Alternate Item Rules

Code: `services/api/src/lumiant/planning/model.py` (`AlternateRule.usable`), `planning/mrp.py` (`_substitute`, two-pass `run_mrp`). Data: canonical `item_alternate`. Tests: S26, S26b–d, S42–S45, C-A.

An alternate is used only when every condition holds:
1. **Approved** (`approved = true`). Similar descriptions are never enough (S26b, S45; the duplicate check marks similar-but-different items `different_specification`, S69).
2. **Valid on the requirement date** (`valid_from` ≤ date < `valid_to`).
3. **Allowed for the customers** the demand is pegged to (`customer_id` restriction; S45).
4. **Within the maximum share** of the requirement (`max_share_pct`; S42).
5. **Free stock of the alternate:** only stock the alternate does not need for its own demand. A first planning pass finds it, and the second pass substitutes (S26c).

**Conversion:** `ratio` alternate units replace one primary unit. 35 units of B at ratio 2 cover 17.5 units of A (S26d). **Order:** rules by `priority`, then alternate id (S43). If the alternates run out, the rest is planned on the primary item (S44).

Each substitution is recorded as coverage source `alternate`, with the rule, ratio and units used, so it shows in the order fulfilment line (`from_alternates`) and can be reviewed. Substitution for buy and make items happens at the requirement level; substitution inside one specific parent's BOM only, and technical compatibility attributes, are planned.
