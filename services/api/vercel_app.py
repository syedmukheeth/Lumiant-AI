"""Entry point for the Vercel deployment (vercel.json service `api`): the FastAPI app for the hosted demo.

Demo posture, on purpose:
- Synthetic tenants only (the bundled `data/synthetic/*.duckdb`); the client extract under `var/` is never uploaded
  (`.vercelignore` whitelists what ships).
- Development sign-in on synthetic data; keep the deployment behind Vercel's deployment protection.
- The application database (audit log, API keys, saved views, alert rules) is SQLite in /tmp: per instance and
  temporary. A lasting deployment sets LUMIANT_APP_DB_URL to a managed PostgreSQL.
- No external AI: without LUMIANT_AGENT_PROVIDER the Analyst runs its offline rules.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))  # src layout: import the package without an install step

os.environ.setdefault("LUMIANT_APP_ENV", "development")
os.environ.setdefault("LUMIANT_AUTH_MODE", "dev")
os.environ.setdefault("LUMIANT_DATA_DIR", str(HERE))
os.environ.setdefault("LUMIANT_APP_DB_URL", "sqlite:////tmp/lumiant-app.db")
os.environ.setdefault("LUMIANT_LOG_LEVEL", "WARNING")
os.environ.setdefault("LUMIANT_COOKIE_SECURE", "true")  # served over https only
# LUMIANT_DEV_JWT_SECRET must be set in the Vercel project (one value for every instance, or sessions break).

from lumiant.main import create_app  # noqa: E402  (after sys.path and environment are set)

app = create_app()
