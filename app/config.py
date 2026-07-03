"""Catálogo de loterías soportadas y configuración global.

Cada lotería declara los *slugs* que usan las distintas fuentes de scraping.
Añadir una nueva lotería es, en la mayoría de los casos, agregar una entrada
a ``LOTTERIES`` (y, si la fuente usa otra ruta, ajustar el parser en scraper.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Nº de sorteos que analiza el motor. Si en la BD hay menos, se usan los disponibles.
ANALYSIS_WINDOW = 70

# Todas las loterías del MVP son de 4 cifras (0000-9999).
DIGITS = 4

# Semilla fija -> las sugerencias son reproducibles (mismo histórico => mismo resultado).
RANDOM_SEED = 20260702


@dataclass(frozen=True)
class Lottery:
    """Definición de una lotería y sus rutas por fuente de datos."""

    slug: str          # identificador interno / URL de la API (ej. "dorado-manana")
    name: str          # nombre visible en la UI
    group: str         # familia ("Dorado", "Chontico") para agrupar en la UI
    # slug tal como lo espera cada fuente. Si una fuente no cubre la lotería, se omite.
    source_slugs: dict[str, str] = field(default_factory=dict)


# Fuentes conocidas (ver scraper.py para los parsers correspondientes).
SOURCE_RESULTADO = "resultadodelaloteria"
SOURCE_COLOMBIA = "colombia"

LOTTERIES: dict[str, Lottery] = {
    "dorado-manana": Lottery(
        slug="dorado-manana",
        name="Dorado Mañana",
        group="Dorado",
        source_slugs={
            SOURCE_RESULTADO: "dorado-manana",
            SOURCE_COLOMBIA: "dorado-manana",
        },
    ),
    "dorado-tarde": Lottery(
        slug="dorado-tarde",
        name="Dorado Tarde",
        group="Dorado",
        source_slugs={
            SOURCE_RESULTADO: "dorado-tarde",
            SOURCE_COLOMBIA: "dorado-tarde",
        },
    ),
    "dorado-noche": Lottery(
        slug="dorado-noche",
        name="Dorado Noche",
        group="Dorado",
        source_slugs={
            SOURCE_RESULTADO: "dorado-noche",
            SOURCE_COLOMBIA: "dorado-noche",
        },
    ),
    "chontico-dia": Lottery(
        slug="chontico-dia",
        name="Chontico Día",
        group="Chontico",
        source_slugs={
            SOURCE_RESULTADO: "chontico-dia",
            SOURCE_COLOMBIA: "chontico-dia",
        },
    ),
    "chontico-noche": Lottery(
        slug="chontico-noche",
        name="Chontico Noche",
        group="Chontico",
        source_slugs={
            SOURCE_RESULTADO: "chontico-noche",
            SOURCE_COLOMBIA: "chontico-noche",
        },
    ),
}


# Texto legal/ético mostrado de forma permanente en la UI y en las respuestas de la API.
DISCLAIMER = (
    "Las loterías son juegos de azar: cada sorteo es independiente y aleatorio. "
    "Ningún análisis estadístico puede predecir resultados futuros ni mejorar tus "
    "probabilidades reales de ganar. Esta herramienta es solo para análisis de datos "
    "históricos y entretenimiento. Juega con responsabilidad."
)


def get_lottery(slug: str) -> Lottery | None:
    """Devuelve la lotería por slug, o None si no existe."""
    return LOTTERIES.get(slug)
