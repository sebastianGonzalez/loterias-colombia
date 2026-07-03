"""Modelos de datos compartidos entre la BD, el motor de análisis y la API."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator


class Draw(BaseModel):
    """Un resultado de sorteo: lotería, fecha y número de 4 cifras."""

    lottery: str
    draw_date: date
    number: str = Field(..., description="Número ganador de 4 cifras, ej. '0263'")
    source: str = ""

    @field_validator("number")
    @classmethod
    def _validate_number(cls, v: str) -> str:
        v = v.strip()
        if not (v.isdigit() and len(v) == 4):
            raise ValueError(f"number debe ser 4 dígitos, recibido: {v!r}")
        return v

    @property
    def digits(self) -> list[int]:
        """Los 4 dígitos como enteros, posición 0 = millar ... posición 3 = unidad."""
        return [int(c) for c in self.number]


class Suggestion(BaseModel):
    """Una de las 3 sugerencias generadas por el motor."""

    number: str
    method: str        # nombre corto del método (ej. "Markov posicional")
    rationale: str     # explicación legible del "por qué"
    score: float       # score relativo (mayor = más respaldado por el histórico)


class PositionStat(BaseModel):
    """Frecuencia de cada dígito 0-9 en una posición concreta."""

    position: int                    # 0..3
    counts: list[int]                # 10 enteros: counts[d] = veces que salió el dígito d
    top_digit: int                   # dígito más frecuente en esta posición


class PredictionResult(BaseModel):
    """Respuesta completa de /api/predict: sugerencias + estadísticas + metadatos."""

    lottery: str
    lottery_name: str
    draws_used: int
    suggestions: list[Suggestion]
    hot_numbers: list[tuple[str, int]]     # (número, frecuencia) más frecuentes
    cold_numbers: list[tuple[str, int]]    # números que no han salido / menos frecuentes
    position_stats: list[PositionStat]
    last_draw: str | None                  # último número conocido
    disclaimer: str
