"""Catálogo de loterías soportadas y configuración global.

Añadir una lotería nueva de 4 cifras suele ser solo agregar una entrada a
``LOTTERIES`` con su slug de fuente. Baloto usa ``kind="baloto"`` por su formato
distinto (5 balotas 1–43 + súper balota 1–16).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Nº de sorteos que analiza el motor. Si en la BD hay menos, se usan los disponibles.
ANALYSIS_WINDOW = 70

# Semilla fija -> sugerencias reproducibles (mismo histórico => mismo resultado).
RANDOM_SEED = 20260702

# Tipos de juego soportados.
KIND_CIFRAS4 = "cifras4"
KIND_BALOTO = "baloto"

# Parámetros de Baloto (formato oficial actual).
BALOTO_MAIN_MAX = 43   # 5 balotas de 1..43
BALOTO_MAIN_COUNT = 5
BALOTO_SUPER_MAX = 16  # 1 súper balota de 1..16


@dataclass(frozen=True)
class Lottery:
    """Definición de una lotería y sus rutas por fuente de datos."""

    slug: str
    name: str
    group: str
    kind: str = KIND_CIFRAS4
    draw_days: str = "Todos los días"
    source_slugs: dict[str, str] = field(default_factory=dict)


SOURCE_RESULTADO = "resultadodelaloteria"
SOURCE_COLOMBIA = "colombia"


def _r(slug: str) -> dict[str, str]:
    """Atajo: la mayoría de loterías usan el mismo slug en la fuente principal."""
    return {SOURCE_RESULTADO: slug}


LOTTERIES: dict[str, Lottery] = {
    # --- Dorado ---
    "dorado-manana": Lottery("dorado-manana", "Dorado Mañana", "Dorado",
                             source_slugs={SOURCE_RESULTADO: "dorado-manana",
                                           SOURCE_COLOMBIA: "dorado-manana"}),
    "dorado-tarde": Lottery("dorado-tarde", "Dorado Tarde", "Dorado",
                            source_slugs={SOURCE_RESULTADO: "dorado-tarde",
                                          SOURCE_COLOMBIA: "dorado-tarde"}),
    "dorado-noche": Lottery("dorado-noche", "Dorado Noche", "Dorado",
                            source_slugs={SOURCE_RESULTADO: "dorado-noche",
                                          SOURCE_COLOMBIA: "dorado-noche"}),
    # --- Chontico ---
    "chontico-dia": Lottery("chontico-dia", "Chontico Día", "Chontico",
                            source_slugs={SOURCE_RESULTADO: "chontico-dia",
                                          SOURCE_COLOMBIA: "chontico-dia"}),
    "chontico-noche": Lottery("chontico-noche", "Chontico Noche", "Chontico",
                              source_slugs={SOURCE_RESULTADO: "chontico-noche",
                                            SOURCE_COLOMBIA: "chontico-noche"}),
    # --- Sinuano ---
    "sinuano-dia": Lottery("sinuano-dia", "Sinuano Día", "Sinuano",
                           source_slugs=_r("sinuano-dia")),
    "sinuano-noche": Lottery("sinuano-noche", "Sinuano Noche", "Sinuano",
                             source_slugs=_r("sinuano-noche")),
    # --- Paisita ---
    "paisita-dia": Lottery("paisita-dia", "Paisita Día", "Paisita",
                           source_slugs=_r("paisita-dia")),
    "paisita-noche": Lottery("paisita-noche", "Paisita Noche", "Paisita",
                             source_slugs=_r("paisita-noche")),
    # --- Caribeña ---
    "caribena-dia": Lottery("caribena-dia", "Caribeña Día", "Caribeña",
                            source_slugs=_r("caribena-dia")),
    "caribena-noche": Lottery("caribena-noche", "Caribeña Noche", "Caribeña",
                              source_slugs=_r("caribena-noche")),
    # --- Otras de 4 cifras ---
    "motilon-tarde": Lottery("motilon-tarde", "Motilón Tarde", "Otras",
                             source_slugs=_r("motilon-tarde")),
    "pijao-de-oro": Lottery("pijao-de-oro", "Pijao de Oro", "Otras",
                            source_slugs=_r("pijao-de-oro")),
    # --- Baloto (formato distinto) ---
    "baloto": Lottery("baloto", "Baloto", "Baloto",
                      kind=KIND_BALOTO, draw_days="Lun, Mié, Sáb",
                      source_slugs=_r("baloto")),
}


# Texto legal/ético mostrado de forma permanente en la UI y en la API.
DISCLAIMER = (
    "Las loterías son juegos de azar: cada sorteo es independiente y aleatorio. "
    "Ningún análisis estadístico puede predecir resultados futuros ni mejorar tus "
    "probabilidades reales de ganar. Esta herramienta es solo para análisis de datos "
    "históricos y entretenimiento. Juega con responsabilidad."
)


def get_lottery(slug: str) -> Lottery | None:
    return LOTTERIES.get(slug)
