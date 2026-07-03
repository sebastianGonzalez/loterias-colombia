"""Tests del motor de análisis: validez, determinismo y Markov."""
from __future__ import annotations

from datetime import date, timedelta

from app.analysis import _markov_transition, analyze
from app.models import Draw


def _make_draws(numbers: list[str]) -> list[Draw]:
    """Crea draws del más reciente al más antiguo (como los entrega la BD)."""
    base = date(2026, 6, 1)
    draws = []
    for i, n in enumerate(numbers):
        # el primero de la lista = más reciente
        draws.append(
            Draw(
                lottery="dorado-manana",
                draw_date=base + timedelta(days=len(numbers) - i),
                number=n,
                source="test",
            )
        )
    return draws


SAMPLE = _make_draws(
    [
        "2679", "8254", "4268", "3646", "8826",
        "9388", "7032", "5181", "0263", "5446",
        "1234", "5678", "9012", "3456", "7890",
    ]
)


def test_returns_three_valid_suggestions():
    result = analyze(SAMPLE, "dorado-manana", "Dorado Mañana")
    assert len(result.suggestions) == 3
    for s in result.suggestions:
        assert s.number.isdigit() and len(s.number) == 4
        assert 0.0 <= s.score <= 1.0


def test_deterministic_same_input_same_output():
    r1 = analyze(SAMPLE, "dorado-manana", "Dorado Mañana")
    r2 = analyze(SAMPLE, "dorado-manana", "Dorado Mañana")
    assert [s.number for s in r1.suggestions] == [s.number for s in r2.suggestions]


def test_draws_used_matches_input():
    result = analyze(SAMPLE, "dorado-manana", "Dorado Mañana")
    assert result.draws_used == len(SAMPLE)
    assert result.last_draw == "2679"


def test_empty_input_is_safe():
    result = analyze([], "dorado-manana", "Dorado Mañana")
    assert result.draws_used == 0
    assert result.suggestions == []
    assert result.last_draw is None


def test_position_stats_shape():
    result = analyze(SAMPLE, "dorado-manana", "Dorado Mañana")
    assert len(result.position_stats) == 4
    for ps in result.position_stats:
        assert len(ps.counts) == 10
        assert sum(ps.counts) == len(SAMPLE)  # cada sorteo aporta 1 dígito por posición
        assert 0 <= ps.top_digit <= 9


def test_markov_rows_are_probability_distributions():
    trans = _markov_transition(SAMPLE)
    assert len(trans) == 4  # una matriz por posición
    for pos_matrix in trans:
        assert len(pos_matrix) == 10
        for row in pos_matrix:
            assert len(row) == 10
            assert abs(sum(row) - 1.0) < 1e-9  # cada fila suma 1


def test_hot_numbers_present():
    # Repetimos un número para forzar que sea "caliente".
    draws = _make_draws(["1111", "1111", "2222", "3333", "1111"])
    result = analyze(draws, "dorado-manana", "Dorado Mañana")
    assert result.hot_numbers[0][0] == "1111"
    assert result.hot_numbers[0][1] == 3
