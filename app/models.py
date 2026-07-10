"""Modelos de datos compartidos entre la BD, el motor de análisis y la API.

El campo ``Draw.numbers`` es genérico y guarda el resultado ya serializado según
el tipo de lotería:
  - 4 cifras -> "0263"
  - Baloto   -> "02-12-16-27-28|12"  (5 balotas principales | súper balota)
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class Draw(BaseModel):
    """Un resultado de sorteo: lotería, fecha y resultado serializado."""

    lottery: str
    draw_date: date
    numbers: str = Field(..., description="Resultado serializado (ver módulo).")
    source: str = ""

    @property
    def digits(self) -> list[int]:
        """Los dígitos como enteros (solo válido para loterías de 4 cifras)."""
        return [int(c) for c in self.numbers if c.isdigit()]

    def baloto_parts(self) -> tuple[list[int], int | None]:
        """Devuelve (balotas principales, súper balota) para Baloto."""
        if "|" in self.numbers:
            main_str, sup_str = self.numbers.split("|", 1)
            main = [int(x) for x in main_str.split("-") if x.strip()]
            sup = int(sup_str) if sup_str.strip() else None
            return main, sup
        main = [int(x) for x in self.numbers.split("-") if x.strip()]
        return main, None


class Suggestion(BaseModel):
    """Una de las 3 sugerencias generadas por el motor."""

    number: str        # texto listo para mostrar ("0263" o "02-12-16-27-28 + 12")
    method: str        # nombre corto del método
    rationale: str     # explicación legible del "por qué"
    score: float       # score relativo (mayor = más respaldado por el histórico)


class PositionStat(BaseModel):
    """Frecuencia de cada dígito 0-9 en una posición (loterías de 4 cifras)."""

    position: int
    counts: list[int]        # 10 enteros
    top_digit: int


class BallStat(BaseModel):
    """Frecuencia de una balota concreta dentro de su rango (Baloto)."""

    number: int
    count: int


class PredictionResult(BaseModel):
    """Respuesta de /api/predict. Campos según el tipo de lotería (``kind``)."""

    lottery: str
    lottery_name: str
    kind: str                              # "cifras4" | "baloto"
    draws_used: int
    suggestions: list[Suggestion]
    last_draw: str | None
    disclaimer: str
    draw_days: str = ""                    # informativo (ej. "Lun, Mié, Sáb")

    # --- Solo para 4 cifras ---
    hot_numbers: list[tuple[str, int]] = []
    cold_numbers: list[tuple[str, int]] = []
    position_stats: list[PositionStat] = []

    # --- Solo para Baloto ---
    ball_stats: list[BallStat] = []        # frecuencia de balotas 1..43
    superball_stats: list[BallStat] = []   # frecuencia de súper balota 1..16
