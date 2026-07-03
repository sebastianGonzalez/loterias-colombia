"""Motor de análisis estadístico para loterías de 4 cifras.

IMPORTANTE (honestidad intelectual): los sorteos son eventos independientes y
aleatorios. Nada de lo que se calcula aquí otorga ventaja predictiva real. Este
módulo describe patrones del histórico y arma 3 "sugerencias" de forma
transparente y **determinista** (misma entrada => misma salida), para uso
analítico y de entretenimiento.

Técnicas implementadas:
  1. Frecuencia por número completo (calientes / fríos).
  2. Frecuencia por posición de dígito (0..3).
  3. Cadenas de Markov por posición: matriz de transición dígito->dígito, usada
     para estimar el dígito "siguiente" partiendo del último resultado.
  4. Features de contexto: suma de dígitos y paridad (informativos en la UI).

Las 3 sugerencias combinan estos enfoques con desempates deterministas.
"""
from __future__ import annotations

import random
from collections import Counter

from .config import DIGITS, RANDOM_SEED
from .models import Draw, PositionStat, PredictionResult, Suggestion


def _position_counts(draws: list[Draw]) -> list[list[int]]:
    """counts[pos][d] = nº de veces que el dígito d apareció en la posición pos."""
    counts = [[0] * 10 for _ in range(DIGITS)]
    for draw in draws:
        for pos, d in enumerate(draw.digits):
            counts[pos][d] += 1
    return counts


def _markov_transition(draws: list[Draw]) -> list[list[list[float]]]:
    """Matriz de transición por posición: M[pos][a][b] = P(dígito b | dígito previo a).

    Se recorre el histórico en orden cronológico (del más antiguo al más reciente)
    contando transiciones dígito(sorteo t) -> dígito(sorteo t+1) por cada posición.
    Filas sin observaciones quedan como distribución uniforme.
    """
    # draws viene del más reciente al más antiguo -> invertir a orden cronológico.
    chrono = list(reversed(draws))
    trans = [[[0.0] * 10 for _ in range(10)] for _ in range(DIGITS)]

    for pos in range(DIGITS):
        for t in range(len(chrono) - 1):
            a = chrono[t].digits[pos]
            b = chrono[t + 1].digits[pos]
            trans[pos][a][b] += 1.0

    # Normalizar cada fila a probabilidades.
    for pos in range(DIGITS):
        for a in range(10):
            total = sum(trans[pos][a])
            if total > 0:
                trans[pos][a] = [c / total for c in trans[pos][a]]
            else:
                trans[pos][a] = [1.0 / 10] * 10
    return trans


def _markov_next_digit(row: list[float], rng: random.Random) -> tuple[int, float]:
    """Dígito más probable de una fila de transición (desempate determinista)."""
    best_p = max(row)
    # Todos los dígitos que empatan en la probabilidad máxima -> elección estable.
    candidates = [d for d, p in enumerate(row) if p == best_p]
    choice = min(candidates)  # desempate determinista por dígito menor
    return choice, best_p


def analyze(
    draws: list[Draw], lottery_slug: str, lottery_name: str
) -> PredictionResult:
    """Ejecuta el estudio completo y genera 3 sugerencias deterministas.

    ``draws`` debe venir del más reciente al más antiguo (como los entrega db.get_last_n).
    """
    rng = random.Random(RANDOM_SEED)
    draws_used = len(draws)

    # --- Frecuencia por número completo ---
    number_counter = Counter(d.number for d in draws)
    hot = number_counter.most_common(5)
    # Fríos: números que aparecieron pero menos (cola de la distribución).
    cold = sorted(number_counter.items(), key=lambda kv: (kv[1], kv[0]))[:5]

    # --- Frecuencia por posición ---
    pos_counts = _position_counts(draws)
    position_stats = [
        PositionStat(
            position=pos,
            counts=pos_counts[pos],
            top_digit=(pos_counts[pos].index(max(pos_counts[pos])) if draws else 0),
        )
        for pos in range(DIGITS)
    ]

    last_number = draws[0].number if draws else None
    suggestions: list[Suggestion] = []

    if draws_used == 0:
        return PredictionResult(
            lottery=lottery_slug,
            lottery_name=lottery_name,
            draws_used=0,
            suggestions=[],
            hot_numbers=[],
            cold_numbers=[],
            position_stats=position_stats,
            last_draw=None,
            disclaimer="",  # main.py rellena el disclaimer global
        )

    # === Sugerencia 1: Markov posicional ===
    trans = _markov_transition(draws)
    last_digits = draws[0].digits
    markov_digits: list[int] = []
    markov_conf: list[float] = []
    for pos in range(DIGITS):
        d, p = _markov_next_digit(trans[pos][last_digits[pos]], rng)
        markov_digits.append(d)
        markov_conf.append(p)
    markov_number = "".join(str(d) for d in markov_digits)
    suggestions.append(
        Suggestion(
            number=markov_number,
            method="Cadena de Markov posicional",
            rationale=(
                "Para cada posición se toma el dígito con mayor probabilidad de "
                f"suceder al último resultado ({draws[0].number}) según la matriz "
                "de transición del histórico."
            ),
            score=round(sum(markov_conf) / DIGITS, 4),
        )
    )

    # === Sugerencia 2: dígitos de mayor frecuencia posicional ===
    freq_digits = [pos_counts[pos].index(max(pos_counts[pos])) for pos in range(DIGITS)]
    freq_number = "".join(str(d) for d in freq_digits)
    freq_score = sum(max(pos_counts[pos]) for pos in range(DIGITS)) / (DIGITS * draws_used)
    suggestions.append(
        Suggestion(
            number=freq_number,
            method="Frecuencia por posición",
            rationale=(
                "Se arma el número con el dígito que más veces ha aparecido en "
                "cada una de las 4 posiciones dentro de la ventana analizada."
            ),
            score=round(freq_score, 4),
        )
    )

    # === Sugerencia 3: mezcla ponderada Markov + frecuencia ===
    # Por posición, se pondera P(markov) contra frecuencia relativa; desempate estable.
    mixed_digits: list[int] = []
    for pos in range(DIGITS):
        total_pos = sum(pos_counts[pos]) or 1
        row = trans[pos][last_digits[pos]]
        combined = [
            0.5 * row[d] + 0.5 * (pos_counts[pos][d] / total_pos) for d in range(10)
        ]
        best = max(combined)
        cand = [d for d, c in enumerate(combined) if c == best]
        mixed_digits.append(min(cand))
    mixed_number = "".join(str(d) for d in mixed_digits)
    suggestions.append(
        Suggestion(
            number=mixed_number,
            method="Mezcla ponderada (Markov + frecuencia)",
            rationale=(
                "Combina al 50/50 la probabilidad de transición de Markov con la "
                "frecuencia posicional, buscando un candidato de consenso."
            ),
            score=round((suggestions[0].score + freq_score) / 2, 4),
        )
    )

    return PredictionResult(
        lottery=lottery_slug,
        lottery_name=lottery_name,
        draws_used=draws_used,
        suggestions=suggestions,
        hot_numbers=[(n, c) for n, c in hot],
        cold_numbers=[(n, c) for n, c in cold],
        position_stats=position_stats,
        last_draw=last_number,
        disclaimer="",
    )
