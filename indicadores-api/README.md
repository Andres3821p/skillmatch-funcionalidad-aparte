# SkillMatch · Servicio de indicadores y pronóstico

API aparte (Python + FastAPI) que calcula indicadores del mercado laboral de SkillMatch, entrena dos modelos
predictivos y sirve la página de tendencias en `/`.

```
API pública de SkillMatch (por defecto) ─┐
MongoDB Atlas (solo lectura, opcional) ──┼──▶ indicadores-api ──▶ /               página (web/)
Datos de demostración (MODO_DEMO=1) ─────┘                    └─▶ /api/indicadores/...  JSON
```

No cambia nada del backend Java: este servicio es independiente y solo **lee**.

## Fuentes de datos

| `FUENTE` | Cuándo se usa | Qué hace falta |
|---|---|---|
| `api` | Por defecto | Nada. Lee `SKILLMATCH_API` (https://skillmatch-yz37.onrender.com/api): `/public/stats`, todas las páginas de `/jobs` y `/companies` |
| `mongo` | Si hay `MONGODB_URI` | Un usuario de MongoDB Atlas de **solo lectura** |
| `demo` | Si `MODO_DEMO=1` | Nada. Datos inventados con tendencia; la página avisa siempre |

Con la fuente `api` la API pública no entrega datos privados (habilidades de las personas, estado y fecha de
cada postulación, vacantes cerradas). Esos endpoints responden `{"disponible": false, "motivo": "..."}` y la página
muestra el motivo. Los datos se guardan 15 minutos y se renuevan en segundo plano: ninguna visita espera las ~40
consultas al sitio, salvo la primera tras arrancar (que además se adelanta al arrancar el servicio).

## Qué calcula

| Endpoint (`/api/indicadores/...`) | Qué devuelve | Con `api` |
|---|---|:-:|
| *(raíz)* | Versión y fuente de datos | Sí |
| `resumen` | Vacantes abiertas, empresas activas, personas, postulaciones por vacante, días en responder, fuente | Sí (sin días en responder) |
| `habilidades-demandadas` | Habilidades más pedidas en vacantes abiertas | Sí |
| `empresas-activas` | Empresas con más vacantes en los últimos 90 días (y postulaciones recibidas) | Sí (sin postulaciones) |
| `habilidades-usuarios` | Habilidades más frecuentes entre las personas (solo totales; se oculta lo que tienen menos de 3) | No |
| `brecha-habilidades` | % de vacantes que piden una habilidad vs. % de personas que la tienen | No |
| `salarios` | Mediana del salario mínimo publicado, por nivel de experiencia | Sí |
| `postulaciones-estado` | Pendientes, revisadas, aceptadas, rechazadas | No |
| `series` | Vacantes y postulaciones por semana | Solo vacantes |
| `pronostico/vacantes`, `pronostico/postulaciones` | **Modelo 1:** pronóstico semanal con rango probable | Solo vacantes |
| `tendencia-habilidades` | **Modelo 2:** habilidades que suben o bajan, con etiqueta de evidencia | Sí |
| `salud` | Health check (no toca la fuente de datos) | Sí |

Documentación interactiva: `http://localhost:8000/docs`.

## Los modelos predictivos

**1. Pronóstico semanal** (`app/prediccion.py`, `pronostico_semanal`). Compara tres modelos con una
prueba hacia atrás (*backtesting*): para cada semana de la segunda mitad del historial predice
usando solo lo anterior y mide el error (MAE):

- promedio de las últimas 4 semanas (la base de comparación),
- tendencia lineal (últimas 12 semanas),
- suavizado exponencial con tendencia amortiguada (Holt), con parámetros ajustados por rejilla.

Se queda con el de menor error; si no le gana al promedio por más de 5 %, usa el promedio. El rango
(80 %) sale del error de la prueba y se ensancha con la distancia. La semana en curso no entrena el
modelo (está incompleta) y las semanas en cero previas al primer dato se descartan. Se necesitan al
menos 8 semanas completas; si no, la API responde `disponible: false` con el motivo.

**2. Habilidades que suben o bajan** (`tendencia_habilidades`). Ajusta una recta al porcentaje semanal
de cada habilidad (últimas 12 semanas). Como con pocas vacantes por semana el azar mueve mucho esos
porcentajes, cada cambio lleva una etiqueta: **firme** si sobrevive al control de falsos positivos
(Benjamini-Hochberg, q = 0,10) o **débil** (podría ser azar).

### Límites que conviene decir en la sustentación

- Son modelos sencillos y transparentes, pensados para pocos datos. No son aprendizaje profundo.
- Con ~10-20 vacantes por semana, detectar que una habilidad sube de verdad es difícil; por eso casi
  todo sale «débil». Es el resultado honesto, no un fallo.
- Si el historial es corto o plano, el pronóstico cae al promedio y la API lo dice en `lectura`.
- Los datos que crea `DataSeeder.java` son aleatorios y uniformes: sobre ellos ningún modelo encontrará
  tendencia real. Con datos reales de uso el pronóstico se vuelve informativo.
- Con la fuente `api` solo se ven las vacantes que **siguen abiertas**: las semanas antiguas pueden verse más
  bajas porque las cerradas ya no aparecen. La respuesta lo dice en `nota` y la página lo muestra.
- Con `MODO_DEMO=1` se usan datos **inventados** con tendencia; la API y la página avisan siempre.

## Privacidad y seguridad

- Con la fuente `api` solo se usan rutas públicas del sitio; el correo y el teléfono de las empresas ya llegan
  ocultos desde el backend.
- Con Mongo, de los usuarios solo se leen los **nombres de sus habilidades** (sin nombre, correo ni ids) y las
  postulaciones se leen sin carta, hoja de vida ni notas. Usa en Atlas un usuario **solo lectura**.
- La API no tiene endpoints de escritura. Si la fuente falla, el error al navegador no incluye detalles.
- La página lleva las mismas cabeceras que el sitio principal: CSP (`script-src 'self'`, `connect-src 'self'`),
  `nosniff`, `Referrer-Policy` y `X-Frame-Options`.

## Probarlo en tu PC

```powershell
cd indicadores-api
.\iniciar.ps1          # datos en vivo de SkillMatch -> http://localhost:8000
.\iniciar.ps1 -Demo    # datos inventados
.\.venv\Scripts\python -m pytest    # 57 pruebas
```

En macOS o Linux:

```bash
cd indicadores-api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
uvicorn app.main:app --reload --port 8000             # FUENTE=demo para datos inventados
```

## Desplegar en Render (plan gratuito)

`render.yaml` (en la raíz del repositorio) crea el servicio `skillmatch-indicadores` con Docker. En Render:
**New → Blueprint**, elegir el repositorio y **Apply**. No hace falta ninguna variable. Para usar Mongo, agregar
`MONGODB_URI` (usuario de solo lectura) en **Environment**.

En el plan gratuito el servicio se duerme tras 15 minutos; la primera visita puede tardar y la página muestra
un aviso mientras despierta.

## Ideas para seguir

- Exponer el clasificador de vacantes de `mineria-datos/` como endpoint (`POST /clasificar`).
- Predicción «cuántas postulaciones recibirá una vacante nueva» (regresión con tipo, modalidad,
  salario y habilidades) cuando haya cientos de postulaciones reales.
- Guardar una foto semanal de los indicadores en una colección propia para tener historia más larga.
- Indicadores por sector, por zona de Cartagena y tiempo hasta la primera postulación.

## Estructura

```
indicadores-api/
├── app/
│   ├── main.py          # endpoints FastAPI, cabeceras de seguridad y la página en /
│   ├── config.py        # variables de entorno y elección de la fuente
│   ├── fuente_api.py    # lectura de la API pública de SkillMatch
│   ├── datos.py         # lectura de MongoDB (solo lectura), caché y renovación en segundo plano
│   ├── indicadores.py   # cálculo de indicadores (funciones puras)
│   ├── prediccion.py    # modelos predictivos
│   └── demo.py          # datos de demostración
├── web/                 # la página (index.html + assets; app.css es el del sitio principal)
├── tests/               # 57 pruebas (API de SkillMatch y MongoDB simuladas)
├── Dockerfile · requirements.txt · requirements-dev.txt · iniciar.ps1 · .env.example
```
