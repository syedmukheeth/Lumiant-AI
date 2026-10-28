# Lumiant Knowledge Base

Everything needed to understand, continue, or audit this project lives in this folder as Markdown.
It is written so that a new engineer **or an LLM with no prior context** can pick up the work safely.

## Reading order (new session / new LLM)

1. `00-context/CURRENT_STATE.md` — where the project is right now, what is verified, what is next.
2. `00-context/CONTEXT_FLOW.md` — how a request flows through the system, and the working loop every session follows.
3. `00-context/PROJECT_BRIEF.md` — what the customer asked for (summary + verbatim master prompt).
4. `00-context/FACTS_ASSUMPTIONS.md` — what is confirmed vs assumed vs unknown. **Do not treat assumptions as facts.**
5. `05-plan/IMPLEMENTATION_PLAN.md` — the checkbox tracker. Pick the next unchecked item.
6. `logs/WORKLOG.md` (latest entries) — what the last session actually did.
7. Then the topic file for the area you are touching (table below).

## Map

| Folder | Purpose | Key files |
|---|---|---|
| `00-context/` | Orientation | `CURRENT_STATE`, `CONTEXT_FLOW`, `PROJECT_BRIEF`, `PROJECT_ASSESSMENT`, `FACTS_ASSUMPTIONS`, `GLOSSARY`, `ENVIRONMENT` |
| `01-product/` | What we build and why | `REQUIREMENTS`, `ACCEPTANCE_CRITERIA`, `AGENT_DESIGN`, `FEATURE_CATALOG`, `ROLES_PERMISSIONS` |
| `02-architecture/` | How it is built | `ARCHITECTURE`, `DATA_MODEL`, `QUERY_ENGINE`, `CONNECTORS`, `MAPPING`, `API_CONTRACTS`, `FRONTEND`, `adr/` |
| `03-security/` | Security design | `SECURITY_PLAN`, `THREAT_MODEL` |
| `04-domain/` | Inventory domain rules | `INVENTORY_CALCULATIONS`, `CLASSIFICATIONS`, `SYNTHETIC_DATA` |
| `05-plan/` | Plan and progress | `ROADMAP`, `IMPLEMENTATION_PLAN`, `MILESTONE_01` |
| `06-operations/` | Running it | `DEV_SETUP`, `TESTING`, `DEPLOYMENT` |
| `07-customer/` | Customer dependencies | `OPEN_QUESTIONS`, `CLIENT_DATA_INTAKE` (SAP exports, structure only) |
| `logs/` | History | `WORKLOG`, `DECISION_LOG`, `TEST_RUNS`, `ISSUES`, `CHANGELOG`, `sessions/` |

## Master-prompt deliverables → where they are

| Deliverable | File |
|---|---|
| PROJECT_ASSESSMENT.md (incl. answers A–J) | `00-context/PROJECT_ASSESSMENT.md` |
| REQUIREMENTS.md | `01-product/REQUIREMENTS.md` |
| OPEN_QUESTIONS.md | `07-customer/OPEN_QUESTIONS.md` |
| ARCHITECTURE.md | `02-architecture/ARCHITECTURE.md` |
| IMPLEMENTATION_PLAN.md | `05-plan/IMPLEMENTATION_PLAN.md` |
| SECURITY_PLAN.md | `03-security/SECURITY_PLAN.md` |

## Status vocabulary (used everywhere)

| Label | Meaning |
|---|---|
| **Verified** | Implemented and proven by an automated test or a recorded manual check (link the evidence). |
| **Implemented (untested)** | Code exists but no test proves it yet. |
| **Simulated** | Works only against synthetic data / dev auth. Not evidence of customer integration. |
| **Designed** | Documented design, no code. |
| **Not started (M#)** | Planned for milestone M#. |
| **Blocked (Q-###)** | Waiting on a customer answer in `07-customer/OPEN_QUESTIONS.md`. |

## Documentation rules

- Docs must describe the code **as it is**. If you change behaviour, update the doc in the same step.
- Never put secrets, credentials, tokens, connection strings or real customer data in any doc or log.
- Logs in `logs/` are append-only (correct mistakes with a new entry, don't rewrite history).
- `CURRENT_STATE.md` is the one file that is rewritten (not appended) at the end of each session.
