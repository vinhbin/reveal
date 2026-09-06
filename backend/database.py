from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from backend.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

from sqlalchemy import event, inspect, text

class Base(DeclarativeBase):
    pass

def _auto_migrate_columns(target, connection, **kw):
    """Automatically adds any new columns from models to existing SQLite tables."""
    try:
        insp = inspect(connection)
        for table_name, table in target.tables.items():
            if insp.has_table(table_name):
                existing_cols = {col["name"] for col in insp.get_columns(table_name)}
                for col in table.columns:
                    if col.name not in existing_cols:
                        col_type = col.type.compile(connection.dialect)
                        sql = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type}"
                        connection.execute(text(sql))
    except Exception:
        pass

event.listen(Base.metadata, "after_create", _auto_migrate_columns)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
