"""Tests del motor: validez, determinismo, Markov (4 cifras) y Baloto."""
from __future__ import annotations

from datetime import date, timedelta

from app.analysis import _markov_transition, analyze
from app.models import Draw


def _make_draws(values: list[str], lottery: str = "sinuano-dia") -> list[Draw]:
    """Crea draws del más reciente al más antiguo (como los entrega la BD)."""
    base = date(2026, 6, 1)
    return [
        Draw(lottery=lottery, draw_date=base + timedelta(days=len(values) - i),
             numbers=v, source="test")
        for i, v in enumerate(values)
    ]


SAMPLE = _make_draws([
    "2679", "8254", "4268", "3646", "8826",
    "9388", "7032", "5181", "0263", "5446",
    "1234", "5678", "9012", "3456", "7890",
])


# ---------------------------- 4 cifras ---------------------------- #
def test_returns_three_valid_suggestions():
    r = analyze(SAMPLE, "sinuano-dia", "Sinuano Día")
    assert r.kind == "cifras4"
    assert len(r.suggestions) == 3
    for s in r.suggestions:
        assert s.number.isdigit() and len(s.number) == 4
        assert 0.0 <= s.score <= 1.0


def test_deterministic():
    r1 = analyze(SAMPLE, "sinuano-dia", "Sinuano Día")
    r2 = analyze(SAMPLE, "sinuano-dia", "Sinuano Día")
    assert [s.number for s in r1.suggestions] == [s.number for s in r2.suggestions]


def test_empty_input_is_safe():
    r = analyze([], "sinuano-dia", "Sinuano Día")
    assert r.draws_used == 0 and r.suggestions == [] and r.last_draw is None


def test_position_stats_shape():
    r = analyze(SAMPLE, "sinuano-dia", "Sinuano Día")
    assert len(r.position_stats) == 4
    for ps in r.position_stats:
        assert len(ps.counts) == 10
        assert sum(ps.counts) == len(SAMPLE)


def test_markov_rows_are_distributions():
    trans = _markov_transition(SAMPLE)
    assert len(trans) == 4
    for pos_matrix in trans:
        for row in pos_matrix:
            assert abs(sum(row) - 1.0) < 1e-9


# ------------------------------ Baloto ---------------------------- #
BALOTO_SAMPLE = _make_draws([
    "02-12-16-27-28|12", "09-14-40-42-43|09", "03-12-13-17-37|14",
    "10-15-22-24-30|03", "15-23-29-33-41|07", "12-14-30-36-43|11",
    "08-12-16-28-33|05", "31-34-37-38-43|02", "16-20-34-37-39|08",
    "04-13-16-22-31|10",
], lottery="baloto")


def test_baloto_three_valid_tickets():
    r = analyze(BALOTO_SAMPLE, "baloto", "Baloto")
    assert r.kind == "baloto"
    assert len(r.suggestions) == 3
    for s in r.suggestions:
        # formato "n - n - n - n - n  +  s"
        main_part, sup_part = s.number.split("+")
        mains = [int(x) for x in main_part.replace("-", " ").split()]
        sup = int(sup_part.strip())
        assert len(mains) == 5
        assert all(1 <= n <= 43 for n in mains)
        assert len(set(mains)) == 5           # sin balotas repetidas
        assert 1 <= sup <= 16


def test_baloto_deterministic():
    r1 = analyze(BALOTO_SAMPLE, "baloto", "Baloto")
    r2 = analyze(BALOTO_SAMPLE, "baloto", "Baloto")
    assert [s.number for s in r1.suggestions] == [s.number for s in r2.suggestions]


def test_baloto_ball_stats_ranges():
    r = analyze(BALOTO_SAMPLE, "baloto", "Baloto")
    assert len(r.ball_stats) == 43
    assert len(r.superball_stats) == 16
    # el total de conteos de balotas = 5 por sorteo
    assert sum(b.count for b in r.ball_stats) == 5 * len(BALOTO_SAMPLE)
