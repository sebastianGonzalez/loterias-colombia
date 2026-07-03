"""Actualiza el histórico de TODAS las loterías. Pensado para correr a diario.

Uso:
    python update_daily.py

Sirve tanto para ejecución manual como para un cron / GitHub Actions.
Devuelve código de salida 0 si al menos una lotería se actualizó sin error.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

from app import scraper


def main() -> int:
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[{stamp}] Iniciando actualización diaria de loterías…")

    results = scraper.refresh_all()

    total_inserted = 0
    errors = 0
    for r in results:
        if "error" in r:
            errors += 1
            print(f"  [ERROR] {r['lottery']}: {r['error']}")
        else:
            total_inserted += r["inserted"]
            print(
                f"  [OK] {r['lottery']}: +{r['inserted']} nuevos "
                f"(total {r['total_stored']}, fuentes: {', '.join(r['sources_used']) or '-'})"
            )

    print(f"Resumen: {total_inserted} sorteos nuevos, {errors} errores.")
    # Éxito si no hubo errores en todas; si todas fallan, código 1.
    return 1 if errors == len(results) else 0


if __name__ == "__main__":
    sys.exit(main())
