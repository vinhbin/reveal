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
