"""Tests de la capa de datos (SQLite): inserción idempotente y queries."""
from __future__ import annotations

from datetime import date

from app import db
from app.models import Draw


def _draw(day: int, numbers: str, lottery: str = "dorado-manana") -> Draw:
    return Draw(
        lottery=lottery,
        draw_date=date(2026, 6, day),
        numbers=numbers,
        source="test",
    )


def test_init_and_insert(tmp_path):
    dbp = tmp_path / "t.db"
    db.init_db(dbp)
    assert db.upsert_draw(_draw(1, "0263"), dbp) is True
    assert db.count_draws("dorado-manana", dbp) == 1


def test_insert_is_idempotent(tmp_path):
    dbp = tmp_path / "t.db"
    db.init_db(dbp)
    assert db.upsert_draw(_draw(1, "0263"), dbp) is True
    assert db.upsert_draw(_draw(1, "9999"), dbp) is False
    assert db.count_draws("dorado-manana", dbp) == 1


def test_upsert_many_counts_new_only(tmp_path):
    dbp = tmp_path / "t.db"
    db.init_db(dbp)
    draws = [_draw(1, "1111"), _draw(2, "2222"), _draw(1, "3333")]
    assert db.upsert_many(draws, dbp) == 2
    assert db.count_draws("dorado-manana", dbp) == 2


def test_get_last_n_orders_desc(tmp_path):
    dbp = tmp_path / "t.db"
    db.init_db(dbp)
    db.upsert_many([_draw(1, "1111"), _draw(3, "3333"), _draw(2, "2222")], dbp)
    last = db.get_last_n("dorado-manana", 2, dbp)
    assert [d.numbers for d in last] == ["3333", "2222"]


def test_lotteries_are_isolated(tmp_path):
    dbp = tmp_path / "t.db"
    db.init_db(dbp)
    db.upsert_draw(_draw(1, "1111", "dorado-manana"), dbp)
    db.upsert_draw(_draw(1, "2222", "chontico-dia"), dbp)
    assert db.count_draws("dorado-manana", dbp) == 1
    assert db.count_draws("chontico-dia", dbp) == 1


def test_baloto_numbers_roundtrip(tmp_path):
    dbp = tmp_path / "t.db"
    db.init_db(dbp)
    db.upsert_draw(_draw(1, "02-12-16-27-28|12", "baloto"), dbp)
    got = db.get_last_n("baloto", 1, dbp)[0]
    main, sup = got.baloto_parts()
    assert main == [2, 12, 16, 27, 28]
    assert sup == 12


def test_extra_serie_and_signo_roundtrip(tmp_path):
    dbp = tmp_path / "t.db"
    db.init_db(dbp)
    db.upsert_draw(_draw(1, "0554#Serie 463", "loteria-de-bogota"), dbp)
    db.upsert_draw(_draw(1, "9423#Virgo", "astro-sol"), dbp)
    bog = db.get_last_n("loteria-de-bogota", 1, dbp)[0]
    astro = db.get_last_n("astro-sol", 1, dbp)[0]
    assert bog.main4 == "0554" and bog.extra == "Serie 463"
    assert astro.main4 == "9423" and astro.extra == "Virgo"
    assert bog.digits == [0, 5, 5, 4]
