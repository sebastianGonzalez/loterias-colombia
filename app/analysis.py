"""Motor de análisis estadístico. Despacha según el tipo de lotería (``kind``).

IMPORTANTE (honestidad intelectual): los sorteos son eventos independientes y
aleatorios. Nada de lo aquí calculado otorga ventaja predictiva real. El módulo
describe patrones del histórico y arma 3 "sugerencias" de forma transparente y
**determinista** (misma entrada => misma salida), para uso analítico.

- 4 cifras: frecuencia por número, calientes/fríos, frecuencia por posición y
  cadenas de Markov por posición.
- Baloto: frecuencia de cada balota (1–43) y de la súper (1–16); 3 tiquetes
  sugeridos de 5+1. Al ser conjuntos (no posiciones), Markov no aplica.
"""
from __future__ import annotations

import random
from collections import Counter

from .config import (
    BALOTO_MAIN_COUNT,
    BALOTO_MAIN_MAX,
    BALOTO_SUPER_MAX,
    KIND_BALOTO,
    RANDOM_SEED,
    get_lottery,
)
from .models import (
    BallStat,
    Draw,
    PositionStat,
    PredictionResult,
    Suggestion,
)

DIGITS = 4  # loterías de 4 cifras

def _fmt_baloto(main: list[int], sup: int) -> str:
    """Formato legible para la UI: '02 - 12 - 16 - 27 - 28  +  12'."""
    return " - ".join(f"{n:02d}" for n in sorted(main)) + f"  +  {sup:02d}"


def _analyze_baloto(
    draws: list[Draw], slug: str, name: str, draw_days: str
) -> PredictionResult:
    rng = random.Random(RANDOM_SEED)
    draws_used = len(draws)

    # Frecuencia de balotas principales (1..43) y de la súper (1..16).
    main_counter: Counter[int] = Counter()
    super_counter: Counter[int] = Counter()
    for d in draws:
        main, sup = d.baloto_parts()
        main_counter.update(main)
        if sup is not None:
            super_counter[sup] += 1

    ball_stats = [
        BallStat(number=n, count=main_counter.get(n, 0))
        for n in range(1, BALOTO_MAIN_MAX + 1)
    ]
    super_stats = [
        BallStat(number=n, count=super_counter.get(n, 0))
        for n in range(1, BALOTO_SUPER_MAX + 1)
    ]

    # Balotas ordenadas por frecuencia (desempate determinista por número).
    ranked_main = sorted(range(1, BALOTO_MAIN_MAX + 1),
                         key=lambda n: (-main_counter.get(n, 0), n))
    top_super = min(range(1, BALOTO_SUPER_MAX + 1),
                    key=lambda n: (-super_counter.get(n, 0), n))

    total_main = sum(main_counter.values()) or 1
    suggestions: list[Suggestion] = []

    # 1) Las 5 más frecuentes + súper más frecuente.
    s1_main = sorted(ranked_main[:BALOTO_MAIN_COUNT])
    s1_score = sum(main_counter.get(n, 0) for n in s1_main) / total_main
    suggestions.append(
        Suggestion(
            number=_fmt_baloto(s1_main, top_super),
            method="Balotas más frecuentes",
            rationale=(
                "Las 5 balotas que más veces han salido en la ventana analizada, "
                "más la súper balota más frecuente."
            ),
            score=round(s1_score, 4),
        )
    )

    # 2) Selección ponderada por frecuencia (muestreo determinista con seed fijo).
    weights = [main_counter.get(n, 0) + 1 for n in range(1, BALOTO_MAIN_MAX + 1)]
    pool = list(range(1, BALOTO_MAIN_MAX + 1))
    s2_main: list[int] = []
    w = weights[:]
    p = pool[:]
    for _ in range(BALOTO_MAIN_COUNT):
        pick = rng.choices(p, weights=w, k=1)[0]
        idx = p.index(pick)
        s2_main.append(pick)
        p.pop(idx)
        w.pop(idx)
    s2_super = rng.choices(
        range(1, BALOTO_SUPER_MAX + 1),
        weights=[super_counter.get(n, 0) + 1 for n in range(1, BALOTO_SUPER_MAX + 1)],
        k=1,
    )[0]
    suggestions.append(
        Suggestion(
            number=_fmt_baloto(sorted(s2_main), s2_super),
            method="Muestreo ponderado por frecuencia",
            rationale=(
                "Selección aleatoria pero ponderada: las balotas más frecuentes "
                "tienen más peso. Reproducible (semilla fija)."
            ),
            score=round(sum(main_counter.get(n, 0) for n in s2_main) / total_main, 4),
        )
    )

    # 3) Tiquete balanceado por rangos (bajo 1-14, medio 15-29, alto 30-43).
    def _top_in_range(lo: int, hi: int, k: int) -> list[int]:
        cand = sorted(range(lo, hi + 1), key=lambda n: (-main_counter.get(n, 0), n))
        return cand[:k]

    s3_main = sorted(set(_top_in_range(1, 14, 2) + _top_in_range(15, 29, 2) + _top_in_range(30, 43, 1)))
    # Completar si por colisión quedaran menos de 5.
    for n in ranked_main:
        if len(s3_main) >= BALOTO_MAIN_COUNT:
            break
        if n not in s3_main:
            s3_main.append(n)
    s3_main = sorted(s3_main[:BALOTO_MAIN_COUNT])
    suggestions.append(
        Suggestion(
            number=_fmt_baloto(s3_main, top_super),
            method="Tiquete balanceado por rangos",
            rationale=(
                "Combina balotas frecuentes de los rangos bajo (1–14), medio (15–29) "
                "y alto (30–43) para un tiquete repartido en todo el rango."
            ),
            score=round(sum(main_counter.get(n, 0) for n in s3_main) / total_main, 4),
        )
    )

    last_main, last_sup = draws[0].baloto_parts()
    return PredictionResult(
        lottery=slug,
        lottery_name=name,
        kind=KIND_BALOTO,
        draws_used=draws_used,
        suggestions=suggestions,
        last_draw=_fmt_baloto(last_main, last_sup) if last_sup is not None else None,
        disclaimer="",
        draw_days=draw_days,
        ball_stats=ball_stats,
        superball_stats=super_stats,
    )


def analyze(draws: list[Draw], lottery_slug: str, lottery_name: str) -> PredictionResult:
    """Punto de entrada: despacha según el tipo de lotería.

    ``draws`` viene del más reciente al más antiguo (como db.get_last_n).
    """
    lot = get_lottery(lottery_slug)
    kind = lot.kind if lot else "cifras4"
    draw_days = lot.draw_days if lot else ""

    if not draws:
        return PredictionResult(
            lottery=lottery_slug,
            lottery_name=lottery_name,
            kind=kind,
            draws_used=0,
            suggestions=[],
            last_draw=None,
            disclaimer="",
            draw_days=draw_days,
        )

    if kind == KIND_BALOTO:
        return _analyze_baloto(draws, lottery_slug, lottery_name, draw_days)
    return _analyze_cifras4(draws, lottery_slug, lottery_name, draw_days)


def _position_counts(draws: list[Draw]) -> list[list[int]]:
    """counts[pos][d] = nº de veces que el dígito d apareció en la posición pos."""
    counts = [[0] * 10 for _ in range(DIGITS)]
    for draw in draws:
        digs = draw.digits
        if len(digs) != DIGITS:
            continue
        for pos, d in enumerate(digs):
            counts[pos][d] += 1
    return counts


def _markov_transition(draws: list[Draw]) -> list[list[list[float]]]:
    """Matriz de transición por posición: M[pos][a][b] = P(dígito b | dígito previo a)."""
    chrono = list(reversed(draws))  # del más antiguo al más reciente
    trans = [[[0.0] * 10 for _ in range(10)] for _ in range(DIGITS)]
    for pos in range(DIGITS):
        for t in range(len(chrono) - 1):
            a = chrono[t].digits[pos]
            b = chrono[t + 1].digits[pos]
            trans[pos][a][b] += 1.0
    for pos in range(DIGITS):
        for a in range(10):
            total = sum(trans[pos][a])
            trans[pos][a] = (
                [c / total for c in trans[pos][a]] if total > 0 else [0.1] * 10
            )
    return trans


def _analyze_cifras4(
    draws: list[Draw], slug: str, name: str, draw_days: str
) -> PredictionResult:
    draws_used = len(draws)

    number_counter = Counter(d.main4 for d in draws)
    hot = number_counter.most_common(5)
    cold = sorted(number_counter.items(), key=lambda kv: (kv[1], kv[0]))[:5]

    pos_counts = _position_counts(draws)
    position_stats = [
        PositionStat(
            position=pos,
            counts=pos_counts[pos],
            top_digit=pos_counts[pos].index(max(pos_counts[pos])),
        )
        for pos in range(DIGITS)
    ]

    suggestions: list[Suggestion] = []
    trans = _markov_transition(draws)
    last_digits = draws[0].digits

    # 1) Markov posicional
    markov_digits, markov_conf = [], []
    for pos in range(DIGITS):
        row = trans[pos][last_digits[pos]]
        best_p = max(row)
        markov_digits.append(min(d for d, p in enumerate(row) if p == best_p))
        markov_conf.append(best_p)
    suggestions.append(
        Suggestion(
            number="".join(str(d) for d in markov_digits),
            method="Cadena de Markov posicional",
            rationale=(
                "Para cada posición se toma el dígito con mayor probabilidad de "
                f"suceder al último resultado ({draws[0].main4}) según la matriz "
                "de transición del histórico."
            ),
            score=round(sum(markov_conf) / DIGITS, 4),
        )
    )

    # 2) Frecuencia por posición
    freq_digits = [pos_counts[pos].index(max(pos_counts[pos])) for pos in range(DIGITS)]
    freq_score = sum(max(pos_counts[pos]) for pos in range(DIGITS)) / (DIGITS * draws_used)
    suggestions.append(
        Suggestion(
            number="".join(str(d) for d in freq_digits),
            method="Frecuencia por posición",
            rationale=(
                "Se arma el número con el dígito que más veces ha aparecido en cada "
                "una de las 4 posiciones dentro de la ventana analizada."
            ),
            score=round(freq_score, 4),
        )
    )

    # 3) Mezcla ponderada Markov + frecuencia
    mixed_digits = []
    for pos in range(DIGITS):
        total_pos = sum(pos_counts[pos]) or 1
        row = trans[pos][last_digits[pos]]
        combined = [0.5 * row[d] + 0.5 * (pos_counts[pos][d] / total_pos) for d in range(10)]
        best = max(combined)
        mixed_digits.append(min(d for d, c in enumerate(combined) if c == best))
    suggestions.append(
        Suggestion(
            number="".join(str(d) for d in mixed_digits),
            method="Mezcla ponderada (Markov + frecuencia)",
            rationale=(
                "Combina al 50/50 la probabilidad de transición de Markov con la "
                "frecuencia posicional, buscando un candidato de consenso."
            ),
            score=round((suggestions[0].score + freq_score) / 2, 4),
        )
    )

    return PredictionResult(
        lottery=slug,
        lottery_name=name,
        kind="cifras4",
        draws_used=draws_used,
        suggestions=suggestions,
        last_draw=draws[0].main4,
        disclaimer="",
        draw_days=draw_days,
        last_extra=draws[0].extra,
        extra_label=(get_lottery(slug).extra_label if get_lottery(slug) else ""),
        hot_numbers=[(n, c) for n, c in hot],
        cold_numbers=[(n, c) for n, c in cold],
        position_stats=position_stats,
    )
