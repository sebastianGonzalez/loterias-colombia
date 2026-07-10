"""API FastAPI: sirve la SPA y expone los endpoints de análisis.

Rutas:
  GET  /                       -> SPA (static/index.html)
  GET  /api/lotteries          -> catálogo de loterías
  POST /api/refresh/{lottery}  -> raspa fuentes y actualiza el histórico
  GET  /api/predict/{lottery}  -> analiza últimos 70 y devuelve 3 sugerencias
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db, scraper
from .analysis import analyze
from .config import ANALYSIS_WINDOW, DISCLAIMER, LOTTERIES, get_lottery

_STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Análisis de Loterías Colombia", version="1.0.0")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


@app.get("/api/lotteries")
def list_lotteries() -> dict:
    """Catálogo de loterías agrupadas, con cuántos sorteos hay almacenados."""
    items = []
    for slug, lot in LOTTERIES.items():
        items.append(
            {
                "slug": slug,
                "name": lot.name,
                "group": lot.group,
                "kind": lot.kind,
                "draw_days": lot.draw_days,
                "extra_label": lot.extra_label,
                "stored": db.count_draws(slug),
            }
        )
    return {"lotteries": items, "window": ANALYSIS_WINDOW, "disclaimer": DISCLAIMER}


@app.post("/api/refresh/{lottery}")
def refresh_lottery(lottery: str) -> dict:
    """Raspa las fuentes públicas y actualiza el histórico de la lotería."""
    if get_lottery(lottery) is None:
        raise HTTPException(status_code=404, detail="Lotería desconocida")
    try:
        return scraper.refresh(lottery)
    except Exception as exc:  # noqa: BLE001 - se reporta el error al cliente
        raise HTTPException(status_code=502, detail=f"Error al actualizar: {exc}")


@app.post("/api/refresh-all")
def refresh_all_lotteries() -> dict:
    """Actualiza TODAS las loterías del catálogo. Puede tardar (son ~28)."""
    results = scraper.refresh_all()
    total_inserted = sum(r.get("inserted", 0) for r in results)
    errors = [r["lottery"] for r in results if "error" in r]
    return {
        "total_inserted": total_inserted,
        "lotteries_updated": len(results) - len(errors),
        "errors": errors,
        "results": results,
    }


@app.get("/api/predict/{lottery}")
def predict(lottery: str) -> dict:
    """Ejecuta el estudio sobre los últimos ``ANALYSIS_WINDOW`` sorteos."""
    lot = get_lottery(lottery)
    if lot is None:
        raise HTTPException(status_code=404, detail="Lotería desconocida")

    draws = db.get_last_n(lottery, ANALYSIS_WINDOW)
    if not draws:
        raise HTTPException(
            status_code=409,
            detail=(
                "No hay datos almacenados para esta lotería. Usa el botón de "
                "actualizar (o POST /api/refresh) para poblar el histórico primero."
            ),
        )

    result = analyze(draws, lot.slug, lot.name)
    result.disclaimer = DISCLAIMER
    return result.model_dump()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


# Archivos estáticos (css/js). Se monta al final para no tapar las rutas /api.
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
