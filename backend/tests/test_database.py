from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import Boolean, Column, MetaData, Table
from sqlalchemy.dialects import postgresql, sqlite

from backend.database import _auto_migrate_columns


@pytest.mark.parametrize("dialect", [postgresql.dialect(), sqlite.dialect()])
def test_legacy_boolean_column_uses_valid_database_default(monkeypatch, dialect):
    metadata = MetaData()
    Table("findings", metadata, Column("needs_re_review", Boolean))
    inspector = Mock()
    inspector.has_table.return_value = True
    inspector.get_columns.return_value = []
    monkeypatch.setattr("backend.database.inspect", lambda connection: inspector)
    statements = []
    connection = SimpleNamespace(
        dialect=dialect,
        execute=lambda statement: statements.append(str(statement)),
    )

    _auto_migrate_columns(metadata, connection)

    # PostgreSQL rejects integer defaults for BOOLEAN, unlike SQLite.
    expected_default = "false" if dialect.name == "postgresql" else "0"
    assert statements[0].lower().endswith(f"default {expected_default}")
    assert len(statements) == 2
    assert "where needs_re_review is null" in statements[1].lower()


def test_migration_failure_prevents_startup_with_incomplete_schema(monkeypatch):
    def fail_inspection(connection):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("backend.database.inspect", fail_inspection)
    with pytest.raises(RuntimeError, match="database unavailable"):
        _auto_migrate_columns(MetaData(), Mock())


def test_database_reconnects_after_idle_connection_is_closed(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path

    env = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{(tmp_path / 'disconnect.db').as_posix()}"}
    probe = """
import asyncio
from sqlalchemy import text
from backend.database import engine

async def main():
    try:
        async with engine.connect() as connection:
            raw = await connection.get_raw_connection()
            driver = raw.driver_connection
            assert (await connection.execute(text('SELECT 1'))).scalar() == 1
        # Simulate the server closing an idle connection retained by the pool.
        await driver.close()
        async with engine.connect() as connection:
            assert (await connection.execute(text('SELECT 1'))).scalar() == 1
    finally:
        await engine.dispose()

asyncio.run(main())
"""
    result = subprocess.run(
        [sys.executable, "-c", probe], env=env,
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
