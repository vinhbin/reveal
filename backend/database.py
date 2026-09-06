from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from backend.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

from sqlalchemy import event, inspect, text

class Base(DeclarativeBase):
    pass

def _auto_migrate_columns(target, connection, **kw):
    """Automatically adds any new columns from models to existing SQLite tables and backfills defaults."""
    try:
        insp = inspect(connection)
        for table_name, table in target.tables.items():
            if insp.has_table(table_name):
                existing_cols = {col["name"] for col in insp.get_columns(table_name)}
                for col in table.columns:
                    if col.name not in existing_cols:
                        col_type = col.type.compile(connection.dialect)
                        default_clause = ""
                        if col.name == "needs_re_review":
                            default_clause = " DEFAULT 0"
                        elif col.name in ("start_byte", "end_byte"):
                            default_clause = " DEFAULT 0"
                        sql = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type}{default_clause}"
                        connection.execute(text(sql))
        if insp.has_table("findings"):
            connection.execute(text("UPDATE findings SET needs_re_review = 0 WHERE needs_re_review IS NULL"))
    except Exception as e:
        import logging
        logging.getLogger("reveal.database").warning(f"Auto-migration notice: {e}")

event.listen(Base.metadata, "after_create", _auto_migrate_columns)

async def init_db(target_engine=None):
    use_engine = target_engine or engine
    async with use_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
