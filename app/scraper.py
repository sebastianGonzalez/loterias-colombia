"""Scraping de resultados históricos de loterías colombianas de 4 cifras.

Diseño:
  - Un parser por fuente. Cada uno devuelve una lista de ``Draw`` normalizados.
  - ``refresh(lottery)`` intenta las fuentes en orden y hace *fallback* si una falla.
  - Todo resultado se persiste de forma idempotente (ver db.upsert_many), de modo
    que el histórico se acumula ejecución tras ejecución hasta superar los 70.

Buenas prácticas: User-Agent identificable, timeouts, solo lectura y sin carga
agresiva sobre las fuentes públicas. Ver README para las notas de términos de uso.
"""
from __future__ import annotations

import re
from datetime import date

import httpx
from bs4 import BeautifulSoup

try:
    # En Windows/macOS, usa el almacén de certificados del SO para evitar
    # errores "CERTIFICATE_VERIFY_FAILED" al conectar por HTTPS.
    import truststore

    truststore.inject_into_ssl()
except Exception:  # pragma: no cover - si no está, se usa el bundle por defecto
    pass

from . import db
from .config import (
    SOURCE_COLOMBIA,
    SOURCE_RESULTADO,
    Lottery,
    get_lottery,
)
from .models import Draw

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; LoteriaStatsBot/1.0; educational statistics research)"
    )
}
_TIMEOUT = httpx.Timeout(20.0)

# DD/MM/YYYY
_DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
_NUM4_RE = re.compile(r"\b(\d{4})\b")


def _parse_ddmmyyyy(text: str) -> date | None:
    m = _DATE_RE.search(text)
    if not m:
        return None
    d, mo, y = (int(g) for g in m.groups())
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def _fetch(url: str) -> str:
    resp = httpx.get(url, headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


# --------------------------------------------------------------------------- #
# Parsers por fuente                                                          #
# --------------------------------------------------------------------------- #
def parse_resultadodelaloteria(html: str, lottery_slug: str) -> list[Draw]:
    """Fuente resultadodelaloteria.com.

    La tabla de resultados tiene columnas: # Sorteo | Fecha (DD/MM/YYYY) | Resultado.
    """
    soup = BeautifulSoup(html, "html.parser")
    draws: list[Draw] = []
    for table in soup.find_all("table"):
        header = table.get_text(" ", strip=True).lower()
        if "resultado" not in header or "fecha" not in header:
            continue
        for tr in table.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if len(cells) < 3:
                continue
            row_text = " ".join(cells)
            draw_date = _parse_ddmmyyyy(row_text)
            if draw_date is None:
                continue
            # El número es la última celda con 4 dígitos.
            number = None
            for c in reversed(cells):
                m = _NUM4_RE.search(c)
                if m:
                    number = m.group(1)
                    break
            if not number:
                continue
            draws.append(
                Draw(
                    lottery=lottery_slug,
                    draw_date=draw_date,
                    number=number,
                    source=SOURCE_RESULTADO,
                )
            )
        if draws:
            break
    return draws


def parse_colombia(html: str, lottery_slug: str) -> list[Draw]:
    """Fuente colombia.com: lista de sorteos recientes (fecha textual + número).

    El número ganador aparece como 4 dígitos; la fecha en formato largo en español.
    Como respaldo del formato DD/MM/YYYY, también se intenta la fecha larga.
    """
    soup = BeautifulSoup(html, "html.parser")
    text_blocks = soup.find_all(["article", "li", "div", "tr"])
    draws: list[Draw] = []
    meses = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
        "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10,
        "noviembre": 11, "diciembre": 12,
    }
    long_date_re = re.compile(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", re.IGNORECASE)
    seen: set[str] = set()
    for block in text_blocks:
        txt = block.get_text(" ", strip=True)
        if len(txt) > 300:
            continue

        # Detectar y extraer la fecha (larga o DD/MM/YYYY).
        d = _parse_ddmmyyyy(txt)
        lm = long_date_re.search(txt)
        if d is None and lm:
            day = int(lm.group(1))
            mon = meses.get(lm.group(2).lower())
            yr = int(lm.group(3))
            if mon:
                try:
                    d = date(yr, mon, day)
                except ValueError:
                    d = None
        if d is None:
            continue

        # Quitar del texto la fecha (y el año) antes de buscar el número ganador,
        # para no confundir el año (p. ej. "2026") con el resultado de 4 cifras.
        cleaned = _DATE_RE.sub(" ", txt)
        if lm:
            cleaned = cleaned.replace(lm.group(0), " ")
        # Quitar solo el año de ESTA fecha (no cualquier 4 dígitos, que podría ser
        # un número ganador legítimo como "2026").
        cleaned = cleaned.replace(str(d.year), " ")
        num_m = _NUM4_RE.search(cleaned)
        if not num_m:
            continue

        key = d.isoformat()
        if key in seen:
            continue
        seen.add(key)
        draws.append(
            Draw(
                lottery=lottery_slug,
                draw_date=d,
                number=num_m.group(1),
                source=SOURCE_COLOMBIA,
            )
        )
    return draws


_PARSERS = {
    SOURCE_RESULTADO: (
        "https://resultadodelaloteria.com/colombia/{slug}",
        parse_resultadodelaloteria,
    ),
    SOURCE_COLOMBIA: (
        "https://www.colombia.com/loterias/{slug}",
        parse_colombia,
    ),
}


def scrape_source(lottery: Lottery, source: str) -> list[Draw]:
    """Raspa una fuente concreta para una lotería. Devuelve [] si falla."""
    if source not in _PARSERS or source not in lottery.source_slugs:
        return []
    url_tpl, parser = _PARSERS[source]
    url = url_tpl.format(slug=lottery.source_slugs[source])
    try:
        html = _fetch(url)
    except (httpx.HTTPError, httpx.TimeoutException):
        return []
    try:
        return parser(html, lottery.slug)
    except Exception:
        # Un parser roto no debe tumbar todo el refresh; se intenta la siguiente fuente.
        return []


def refresh(lottery_slug: str, db_path=None) -> dict:
    """Actualiza el histórico de una lotería probando las fuentes con fallback.

    Devuelve un resumen: fuentes usadas, filas obtenidas y filas nuevas insertadas.
    """
    lottery = get_lottery(lottery_slug)
    if lottery is None:
        raise ValueError(f"Lotería desconocida: {lottery_slug}")

    kwargs = {"db_path": db_path} if db_path else {}
    db.init_db(**kwargs)

    all_draws: list[Draw] = []
    used_sources: list[str] = []
    # Se intentan todas las fuentes y se combinan (dedup por fecha lo hace SQLite).
    for source in (SOURCE_RESULTADO, SOURCE_COLOMBIA):
        got = scrape_source(lottery, source)
        if got:
            used_sources.append(source)
            all_draws.extend(got)

    inserted = db.upsert_many(all_draws, **kwargs) if all_draws else 0
    return {
        "lottery": lottery_slug,
        "sources_used": used_sources,
        "fetched": len(all_draws),
        "inserted": inserted,
        "total_stored": db.count_draws(lottery_slug, **kwargs),
    }


def refresh_all(db_path=None) -> list[dict]:
    """Actualiza el histórico de TODAS las loterías del catálogo.

    Pensado para ejecutarse a diario (cron / GitHub Actions). Un fallo en una
    lotería no interrumpe las demás.
    """
    from .config import LOTTERIES

    results: list[dict] = []
    for slug in LOTTERIES:
        try:
            results.append(refresh(slug, db_path=db_path))
        except Exception as exc:  # noqa: BLE001 - se registra y se continúa
            results.append({"lottery": slug, "error": str(exc)})
    return results
