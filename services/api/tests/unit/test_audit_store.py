import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command

from lumiant.audit.store import (
    AuditRecord,
    AuditStore,
    AuditUnavailableError,
    _alembic_config,
    run_migrations,
)
from tests.helpers import app_db_url


def test_first_run_creates_missing_directory_and_schema(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'not' / 'yet' / 'there' / 'app.db').as_posix()}"
    run_migrations(url)
    store = AuditStore(url)
    store.record(AuditRecord(tenant_id="t", user_id="u", action="a", decision="allow", status="ok"))
    assert [e.action for e in store.recent("t")] == ["a"]
    with store.engine.connect() as conn:
        assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar() == "0001"
    store.dispose()


@pytest.mark.skipif(not os.environ.get("LUMIANT_TEST_PG_ADMIN_URL"), reason="needs LUMIANT_TEST_PG_ADMIN_URL")
def test_postgresql_migration_roundtrip_and_audit_search(tmp_path: Path) -> None:
    url = app_db_url(tmp_path / "unused.db")
    assert url.startswith("postgresql"), url
    run_migrations(url)
    run_migrations(url)  # idempotent
    store = AuditStore(url)
    assert store.engine.dialect.name == "postgresql"
    for action in ("query.run", "query.denied", "report.export"):
        store.record(
            AuditRecord(tenant_id="t", user_id="u", action=action, decision="allow", status="ok", fields=("a", "b"))
        )
    store.record(AuditRecord(tenant_id="other", user_id="u", action="query.run", decision="deny", status="denied"))
    assert [e.action for e in store.recent("t")] == ["report.export", "query.denied", "query.run"]
    found = store.search("t", limit=10, offset=0, decision="allow", action_prefix="query.")
    assert {e.action for e in found} == {"query.run", "query.denied"}
    assert all(e.occurred_at.tzinfo is not None for e in found)
    assert store.search("t", limit=1, offset=1, decision=None, action_prefix="100%_") == []  # LIKE wildcards escaped
    with store.engine.connect() as conn:
        assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar() == "0001"
    store.dispose()
    command.downgrade(_alembic_config(url), "base")
    store2 = AuditStore(url)
    with pytest.raises(AuditUnavailableError):  # fails closed when the table is gone
        store2.record(AuditRecord(tenant_id="t", user_id="u", action="a", decision="allow", status="ok"))
    store2.dispose()
