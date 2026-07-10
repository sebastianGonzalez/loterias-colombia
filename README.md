# Análisis de Loterías Colombia

Aplicación web que estudia los resultados históricos de loterías colombianas y genera
**3 sugerencias del día** por lotería, respaldadas por estadística, frecuencias y
**cadenas de Markov**. Soporta dos formatos:

- **Loterías de 4 cifras** (Dorado, Chontico, Sinuano, Paisita, Caribeña, Motilón,
  Pijao de Oro): análisis por número completo y por posición de dígito + Markov.
- **Baloto** (5 balotas 1–43 + Súper Balota 1–16, juega Lun/Mié/Sáb): frecuencia de
  balotas y 3 tiquetes sugeridos.

> ⚠️ **Aviso importante.** Las loterías son juegos de azar: cada sorteo es
> independiente y aleatorio. **Ningún análisis puede predecir el resultado futuro ni
> mejorar tus probabilidades reales de ganar.** Esta herramienta es solo para análisis
> de datos históricos y entretenimiento. Juega con responsabilidad.

## Stack

- **Backend:** FastAPI + Uvicorn (Python 3.12)
- **Datos:** SQLAlchemy sobre **Postgres** (producción, persistente) o **SQLite**
  (desarrollo/tests). Scraping con httpx + BeautifulSoup.
- **Frontend:** HTML/CSS/JS puro (sin build), servido por FastAPI
- **Tests:** pytest

### Persistencia (importante)

La app elige el motor según la variable de entorno `DATABASE_URL`:
- Si está definida → **Postgres** (el histórico se acumula y persiste de verdad).
- Si no → **SQLite** local en `data/lottery.db` (solo desarrollo y tests).

En producción, el mismo `DATABASE_URL` se configura en Render (la web) y como secret en
GitHub Actions (el actualizador diario), de modo que ambos leen/escriben la misma base.
Esto resuelve el problema del disco efímero de los planes gratuitos, donde el histórico
"volvía a cero" en cada reinicio.

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

El histórico se **acumula** en la base de datos de forma idempotente (sin duplicados).
Cada fuente publica ~19 sorteos recientes; el sistema analiza los que tenga (lo indica
en "Sorteos analizados") y sigue creciendo con la actualización diaria automática.

## Endpoints de la API

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET  | `/api/lotteries` | Catálogo de loterías + nº de sorteos almacenados |
| POST | `/api/refresh/{lottery}` | Raspa las fuentes y actualiza el histórico |
| GET  | `/api/predict/{lottery}` | Analiza últimos 70 y devuelve 3 sugerencias + stats |

## Cómo funciona el análisis (`app/analysis.py`)

El motor despacha según el tipo de lotería (campo `kind`). Todo es **determinista**
(semilla fija → misma entrada produce siempre la misma salida).

**Loterías de 4 cifras** — sobre los últimos ≤70 sorteos:
- Frecuencia por número completo (calientes / fríos).
- Frecuencia por posición de dígito (Millar, Centena, Decena, Unidad).
- Cadenas de Markov por posición (transición dígito→dígito).
- 3 sugerencias: (1) Markov posicional, (2) frecuencia por posición, (3) mezcla 50/50.

**Baloto** — sobre los últimos ≤70 sorteos:
- Frecuencia de cada balota (1–43) y de la súper balota (1–16).
- 3 tiquetes: (1) las 5 más frecuentes + súper más frecuente, (2) muestreo ponderado
  por frecuencia (reproducible), (3) tiquete balanceado por rangos (bajo/medio/alto).
- Al ser conjuntos (no posiciones), Markov no aplica.

Cada sugerencia incluye una explicación de *por qué* se propuso — nunca como promesa.

## Tests

```bash
.venv/Scripts/python.exe -m pytest -q
```

Cubren (14 tests): inserción idempotente, aislamiento por lotería, ida y vuelta del
formato Baloto, validez y determinismo de las sugerencias (4 cifras y Baloto), matrices
de Markov como distribuciones válidas, y rangos correctos de balotas.

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
