# Análisis de Loterías Colombia

Aplicación web que estudia los resultados históricos de loterías colombianas de
4 cifras (Dorado Mañana/Tarde/Noche y Chontico Día/Noche) y genera **3 sugerencias
del día** por lotería, respaldadas por estadística, frecuencias y **cadenas de Markov**.

> ⚠️ **Aviso importante.** Las loterías son juegos de azar: cada sorteo es
> independiente y aleatorio. **Ningún análisis puede predecir el resultado futuro ni
> mejorar tus probabilidades reales de ganar.** Esta herramienta es solo para análisis
> de datos históricos y entretenimiento. Juega con responsabilidad.

## Stack

- **Backend:** FastAPI + Uvicorn (Python 3.12)
- **Datos:** SQLite (se acumula día a día) + scraping con httpx + BeautifulSoup
- **Frontend:** HTML/CSS/JS puro (sin build), servido por FastAPI
- **Tests:** pytest

## Puesta en marcha

```bash
# 1. Crear entorno virtual (aísla las dependencias del proyecto)
python -m venv .venv

# 2. Instalar dependencias
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # Linux/macOS

# 3. Levantar el servidor
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Abre http://127.0.0.1:8000 en el navegador.

### Uso
1. Elige una lotería en el selector.
2. Pulsa **Actualizar datos** para poblar/actualizar el histórico desde las fuentes públicas.
3. Pulsa **Obtener predicción del día** para ver las 3 sugerencias + estadísticas.

El histórico se **acumula**: cada actualización guarda los sorteos nuevos en
`data/lottery.db`. Al principio habrá menos de 70 sorteos; el sistema analiza los que
tenga (lo indica en "Sorteos analizados") y va completando con el uso diario.

## Endpoints de la API

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET  | `/api/lotteries` | Catálogo de loterías + nº de sorteos almacenados |
| POST | `/api/refresh/{lottery}` | Raspa las fuentes y actualiza el histórico |
| GET  | `/api/predict/{lottery}` | Analiza últimos 70 y devuelve 3 sugerencias + stats |

## Cómo funciona el análisis (`app/analysis.py`)

Sobre los últimos ≤70 sorteos se calcula:
- **Frecuencia por número completo** (calientes / fríos).
- **Frecuencia por posición** de dígito (Millar, Centena, Decena, Unidad).
- **Cadenas de Markov por posición:** matriz de transición dígito→dígito que estima
  el dígito siguiente más probable partiendo del último resultado.

Las **3 sugerencias** combinan estos enfoques de forma **determinista** (semilla fija →
misma entrada produce siempre la misma salida):
1. Markov posicional.
2. Dígitos de mayor frecuencia por posición.
3. Mezcla ponderada 50/50 de las dos anteriores.

Cada sugerencia incluye una explicación de *por qué* se propuso — nunca como promesa.

## Tests

```bash
.venv/Scripts/python.exe -m pytest -q
```

Cubren: inserción idempotente en SQLite, aislamiento por lotería, validez y
determinismo de las sugerencias, y que las matrices de Markov sean distribuciones
de probabilidad válidas.

## Ampliar

Añadir una lotería nueva suele ser solo agregar una entrada a `LOTTERIES` en
[`app/config.py`](app/config.py). Si la fuente usa otra estructura de página, se ajusta
el parser correspondiente en [`app/scraper.py`](app/scraper.py).

## Fuentes de datos

- `resultadodelaloteria.com` — fuente principal (tabla con nº sorteo, fecha, resultado).
- `colombia.com` — fuente secundaria de respaldo.

El scraper usa un `User-Agent` identificable, timeouts y solo lectura, sin carga
agresiva. Revisa los términos de uso de cada sitio antes de un uso intensivo.

## Notas

- No incluye autenticación: está pensada para uso local. Si se expone en red, debería
  añadirse control de acceso.
- La app usa `truststore` para usar el almacén de certificados del sistema operativo y
  evitar errores de SSL al hacer scraping en Windows.
