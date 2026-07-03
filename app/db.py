"""Capa de persistencia con SQLite.

El histórico se acumula día a día: cada inserción es idempotente gracias a la
restricción UNIQUE(lottery, draw_date), de modo que ejecutar el scraper varias
veces no genera duplicados.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from .models import Draw

# data/lottery.db en la raíz del proyecto (../data respecto a este archivo).
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "lottery.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS draws (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    lottery    TEXT NOT NULL,
    draw_date  TEXT NOT NULL,          -- ISO 'YYYY-MM-DD'
    number     TEXT NOT NULL,          -- 4 dígitos
    source     TEXT NOT NULL DEFAULT '',
    UNIQUE(lottery, draw_date)
);
CREATE INDEX IF NOT EXISTS idx_draws_lottery_date
    ON draws (lottery, draw_date DESC);
"""


def _connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    """Crea la tabla e índices si no existen."""
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)


def upsert_draw(draw: Draw, db_path: Path | str = DEFAULT_DB_PATH) -> bool:
    """Inserta un sorteo si no existe ya (por lotería+fecha).

    Devuelve True si insertó una fila nueva, False si ya existía.
    """
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO draws (lottery, draw_date, number, source)
            VALUES (?, ?, ?, ?)
            """,
            (draw.lottery, draw.draw_date.isoformat(), draw.number, draw.source),
        )
        return cur.rowcount > 0


def upsert_many(draws: list[Draw], db_path: Path | str = DEFAULT_DB_PATH) -> int:
    """Inserta varios sorteos de forma idempotente. Devuelve cuántos eran nuevos."""
    inserted = 0
    with _connect(db_path) as conn:
        for draw in draws:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO draws (lottery, draw_date, number, source)
                VALUES (?, ?, ?, ?)
                """,
                (draw.lottery, draw.draw_date.isoformat(), draw.number, draw.source),
            )
            inserted += cur.rowcount
    return inserted


def get_last_n(
    lottery: str, n: int = 70, db_path: Path | str = DEFAULT_DB_PATH
) -> list[Draw]:
    """Devuelve los últimos ``n`` sorteos de una lotería, del más reciente al más antiguo."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT lottery, draw_date, number, source
            FROM draws
            WHERE lottery = ?
            ORDER BY draw_date DESC
            LIMIT ?
            """,
            (lottery, n),
        ).fetchall()
    return [
        Draw(
            lottery=r["lottery"],
            draw_date=date.fromisoformat(r["draw_date"]),
            number=r["number"],
            source=r["source"],
        )
        for r in rows
    ]


def count_draws(lottery: str, db_path: Path | str = DEFAULT_DB_PATH) -> int:
    """Cuenta cuántos sorteos hay almacenados para una lotería."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM draws WHERE lottery = ?", (lottery,)
        ).fetchone()
    return int(row["c"])
