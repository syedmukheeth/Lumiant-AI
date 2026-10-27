from pathlib import Path

import sqlalchemy as sa

from lumiant.audit.store import AuditRecord, AuditStore, run_migrations


def test_first_run_creates_missing_directory_and_schema(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'not' / 'yet' / 'there' / 'app.db').as_posix()}"
    run_migrations(url)
    store = AuditStore(url)
    store.record(AuditRecord(tenant_id="t", user_id="u", action="a", decision="allow", status="ok"))
    assert [e.action for e in store.recent("t")] == ["a"]
    with store.engine.connect() as conn:
        assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar() == "0001"
    store.dispose()
