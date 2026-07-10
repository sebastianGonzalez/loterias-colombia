"""Tests de parseo del scraper: captura del dato extra (Serie / signo)."""
from __future__ import annotations

from app.scraper import parse_baloto, parse_resultadodelaloteria

# HTML mínimo con la estructura real: tabla '# Sorteo | Fecha | Resultado'.
TRAD_HTML = """
<table>
  <tr><th>#</th><th>Sorteo</th><th>Fecha</th><th>Resultado</th></tr>
  <tr><td>2852</td><td>25 de junio de 2026</td><td>0554 Serie 463</td></tr>
  <tr><td>2851</td><td>18 de junio de 2026</td><td>6703 Serie 359</td></tr>
</table>
"""

ASTRO_HTML = """
<table>
  <tr><th>#</th><th>Sorteo</th><th>Fecha</th><th>Resultado</th></tr>
  <tr><td>5475</td><td>8 de julio de 2026</td><td>9423 Virgo</td></tr>
  <tr><td>5474</td><td>7 de julio de 2026</td><td>5622 Capricornio</td></tr>
</table>
"""

CHANCE_HTML = """
<table>
  <tr><th>#</th><th>Sorteo</th><th>Fecha</th><th>Resultado</th></tr>
  <tr><td>100</td><td>8 de julio de 2026</td><td>2836</td></tr>
</table>
"""

BALOTO_HTML = """
<table>
  <tr><th>#</th><th>Sorteo</th><th>Fecha</th><th>Resultado</th></tr>
  <tr><td>2679</td><td>6 de julio de 2026</td>
      <td><span class="res-txt">02 - 12 - 16 - 27 - 28 12</span>
          <span class="res-super">12</span></td></tr>
</table>
"""


def test_parse_traditional_captures_serie():
    draws = parse_resultadodelaloteria(TRAD_HTML, "loteria-de-bogota")
    assert len(draws) == 2
    assert draws[0].main4 == "0554"
    assert draws[0].extra == "Serie 463"


def test_parse_astro_captures_signo():
    draws = parse_resultadodelaloteria(ASTRO_HTML, "astro-sol")
    assert draws[0].main4 == "9423"
    assert draws[0].extra == "Virgo"


def test_parse_plain_chance_has_no_extra():
    draws = parse_resultadodelaloteria(CHANCE_HTML, "dorado-manana")
    assert draws[0].main4 == "2836"
    assert draws[0].extra == ""


def test_parse_baloto_still_works():
    draws = parse_baloto(BALOTO_HTML, "baloto")
    assert len(draws) == 1
    main, sup = draws[0].baloto_parts()
    assert main == [2, 12, 16, 27, 28]
    assert sup == 12
