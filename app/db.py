"""Capa de persistencia dual: Postgres (producción) o SQLite (local/tests).

Elige el motor según la variable de entorno ``DATABASE_URL``:
  - Si está definida  -> Postgres (persistente, compartido web + actualizador).
  - Si no             -> SQLite en ``data/lottery.db`` (desarrollo y tests).

El histórico se acumula: cada inserción es idempotente por la restricción
UNIQUE(lottery, draw_date), así que reejecutar el scraper no duplica sorteos.

El campo ``numbers`` guarda el resultado ya serializado:
  - Loterías de 4 cifras -> "0263"
  - Baloto               -> "02-12-16-27-28|12"  (5 principales | súper balota)
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from sqlalchemy import (
    Column,
    Date,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from .models import Draw

DEFAULT_SQLITE_PATH = Path(__file__).resolve().parent.parent / "data" / "lottery.db"

_metadata = MetaData()

draws_table = Table(
    "draws",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("lottery", String(64), nullable=False),
    Column("draw_date", Date, nullable=False),
    Column("numbers", String(64), nullable=False),
    Column("source", String(64), nullable=False, default=""),
    UniqueConstraint("lottery", "draw_date", name="uq_lottery_date"),
)

# Cache de engines por URL para no recrearlos en cada llamada.
_engines: dict[str, Engine] = {}


def _resolve_url(db_path: Path | str | None) -> str:
    """Determina la URL de conexión de SQLAlchemy.

    Prioridad: db_path explícito (SQLite, para tests) > DATABASE_URL > SQLite por defecto.
    """
    if db_path is not None:
        return f"sqlite:///{Path(db_path)}"

    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        # Render/Neon a veces entregan "postgres://"; SQLAlchemy requiere "postgresql+psycopg://".
        if env_url.startswith("postgres://"):
            env_url = env_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif env_url.startswith("postgresql://"):
            env_url = env_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return env_url

    DEFAULT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_SQLITE_PATH}"


def _get_engine(db_path: Path | str | None = None) -> Engine:
    url = _resolve_url(db_path)
    if url not in _engines:
        connect_args = {}
        if url.startswith("sqlite"):
            # SQLite necesita esto para uso multihilo (FastAPI).
            connect_args = {"check_same_thread": False}
        _engines[url] = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    return _engines[url]


def init_db(db_path: Path | str | None = None) -> None:
    """Crea la tabla e índices si no existen (idempotente en ambos motores)."""
    engine = _get_engine(db_path)
    _metadata.create_all(engine)


def _upsert_stmt(engine: Engine, rows: list[dict]):
    """Construye un INSERT ... ON CONFLICT DO NOTHING según el dialecto."""
    if engine.dialect.name == "postgresql":
        stmt = pg_insert(draws_table).values(rows)
        return stmt.on_conflict_do_nothing(index_elements=["lottery", "draw_date"])
    # SQLite
    stmt = sqlite_insert(draws_table).values(rows)
    return stmt.on_conflict_do_nothing(index_elements=["lottery", "draw_date"])


def upsert_draw(draw: Draw, db_path: Path | str | None = None) -> bool:
    """Inserta un sorteo si no existe (por lotería+fecha). True si era nuevo."""
    return upsert_many([draw], db_path) > 0


def upsert_many(draws: list[Draw], db_path: Path | str | None = None) -> int:
    """Inserta varios sorteos de forma idempotente. Devuelve cuántos eran nuevos."""
    if not draws:
        return 0
    engine = _get_engine(db_path)
    inserted = 0
    with engine.begin() as conn:
        for draw in draws:
            row = {
                "lottery": draw.lottery,
                "draw_date": draw.draw_date,
                "numbers": draw.numbers,
                "source": draw.source,
            }
            result = conn.execute(_upsert_stmt(engine, [row]))
            inserted += result.rowcount or 0
    return inserted


def get_last_n(
    lottery: str, n: int = 70, db_path: Path | str | None = None
) -> list[Draw]:
    """Últimos ``n`` sorteos de una lotería, del más reciente al más antiguo."""
    engine = _get_engine(db_path)
    stmt = (
        select(draws_table)
        .where(draws_table.c.lottery == lottery)
        .order_by(draws_table.c.draw_date.desc())
        .limit(n)
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt).mappings().all()
    return [
        Draw(
            lottery=r["lottery"],
            draw_date=r["draw_date"] if isinstance(r["draw_date"], date)
            else date.fromisoformat(str(r["draw_date"])),
            numbers=r["numbers"],
            source=r["source"],
        )
        for r in rows
    ]


def count_draws(lottery: str, db_path: Path | str | None = None) -> int:
    """Cuántos sorteos hay almacenados para una lotería."""
    engine = _get_engine(db_path)
    stmt = select(func.count()).select_from(draws_table).where(
        draws_table.c.lottery == lottery
    )
    with engine.connect() as conn:
        return int(conn.execute(stmt).scalar() or 0)
