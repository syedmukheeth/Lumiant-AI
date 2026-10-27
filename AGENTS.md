# Agent Instructions (any LLM / coding agent)

This repository keeps its entire context in Markdown so any agent can continue the work safely.

1. Read `docs/00-context/CURRENT_STATE.md` first, then `docs/README.md` for the reading order.
2. Follow the hard rules and logging protocol in `CLAUDE.md` — they apply to every agent, not just Claude.
3. Treat `docs/00-context/FACTS_ASSUMPTIONS.md` as the boundary between what is known and what is assumed. Never upgrade an assumption to a fact without a recorded source.
4. Record your work in `docs/logs/WORKLOG.md` using the template in `docs/00-context/CONTEXT_FLOW.md` §B, and each check you run in `docs/logs/TEST_RUNS.md`.
