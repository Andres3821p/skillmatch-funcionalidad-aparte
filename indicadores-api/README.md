# SkillMatch · Servicio de indicadores y pronóstico

API aparte (Python + FastAPI) que lee la base de datos de SkillMatch, calcula indicadores del
mercado laboral y entrena un modelo predictivo. La página `tendencias.html` la consume por HTTP.

```
 MongoDB Atlas ──(solo lectura)──▶ indicadores-api (FastAPI) ──JSON──▶ tendencias.html + tendencias.js
        ▲                                                                (HTML/CSS/JS del proyecto)
        └── backend Java (Spring Boot): sigue igual, no se toca
```

No cambia nada del backend Java: este servicio es independiente y solo **lee**.

## Qué calcula

| Endpoint (`/api/indicadores/...`) | Qué devuelve |
|---|---|
| `resumen` | Vacantes abiertas, empresas activas, postulaciones por vacante, días en responder, fuente de datos |
| `habilidades-demandadas` | Habilidades más pedidas en vacantes abiertas |
| `empresas-activas` | Empresas con más vacantes en los últimos 90 días (y postulaciones recibidas) |
| `habilidades-usuarios` | Habilidades más frecuentes entre las personas (solo totales; se oculta lo que tienen menos de 3) |
| `brecha-habilidades` | % de vacantes que piden una habilidad vs. % de personas que la tienen |
| `salarios` | Mediana del salario mínimo publicado, por nivel de experiencia |
| `postulaciones-estado` | Pendientes, revisadas, aceptadas, rechazadas |
| `series` | Vacantes y postulaciones por semana |
| `pronostico/vacantes`, `pronostico/postulaciones` | **Modelo 1:** pronóstico semanal con rango probable |
| `tendencia-habilidades` | **Modelo 2:** habilidades que suben o bajan, con etiqueta de evidencia |
| `salud` | Health check (no toca la base) |

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
- Con `MODO_DEMO=1` (o sin `MONGODB_URI`) se usan datos **inventados** con tendencia; la API y la
  página avisan siempre que son de demostración.

## Privacidad

- De los usuarios solo se leen los **nombres de sus habilidades** (sin nombre, correo ni ids).
- Las postulaciones se leen sin carta, hoja de vida ni notas.
- La API no tiene endpoints de escritura. Usa en Atlas un usuario de base de datos **solo lectura**.
- Si Mongo falla, el error al navegador no incluye la cadena de conexión.

## Probarlo en tu PC

```bash
cd indicadores-api
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest                                                   # 38 pruebas

# 1) Con datos de demostración (sin base de datos)
MODO_DEMO=1 uvicorn app.main:app --reload --port 8000     # Windows PowerShell: $env:MODO_DEMO=1; uvicorn ...

# 2) Con tu MongoDB (el mismo de la app)
MONGODB_URI="mongodb+srv://usuario_lectura:clave@cluster0.xxxxx.mongodb.net/skillmatch" \
  uvicorn app.main:app --port 8000
```

Luego abre el frontend con Live Server (`SkillMatch/src/pages/tendencias.html`). `indicadores-config.js` detecta
que estás en local y llama a `http://localhost:8000`.

## Integrarlo al proyecto

1. Copia a tu repositorio, respetando las carpetas:
   - `indicadores-api/` (carpeta nueva, en la raíz)
   - `SkillMatch/src/pages/tendencias.html`
   - `SkillMatch/src/assets/js/tendencias.js`, `indicadores-config.js` e `indicadores-inicio.js`
   - `SkillMatch/src/assets/css/tendencias.css`
   - `SkillMatch/src/pages/dashboard.html` (solo añade un enlace a la página nueva)
2. En producción, en `assets/js/indicadores-config.js` pon la dirección del servicio en `API_INDICADORES`.
3. En el servicio, `ALLOWED_ORIGINS` = la URL del sitio (CORS).

La política de seguridad (CSP) de `SecurityConfig.java` ya permite `connect-src https:`, así que el
sitio puede llamar a la API publicada sin tocar el backend. `tendencias.css` solo usa los tokens de
`app.css`; si prefieres un único archivo, pega su contenido al final de `app.css`.

## Desplegar en Render (plan gratuito)

Añade un segundo servicio a `render.yaml`:

```yaml
  - type: web
    name: skillmatch-indicadores
    runtime: docker
    dockerfilePath: ./indicadores-api/Dockerfile
    dockerContext: ./indicadores-api
    healthCheckPath: /api/indicadores/salud
    envVars:
      - key: MONGODB_URI        # usuario de SOLO LECTURA
        sync: false
      - key: ALLOWED_ORIGINS
        value: https://skillmatch-yz37.onrender.com
```

En el plan gratuito el servicio se duerme tras 15 minutos y la primera visita tarda hasta un minuto:
la página muestra un aviso mientras despierta.

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
│   ├── main.py          # endpoints FastAPI y CORS
│   ├── datos.py         # lectura de MongoDB (solo lectura) y caché
│   ├── indicadores.py   # cálculo de indicadores (funciones puras)
│   ├── prediccion.py    # modelos predictivos
│   ├── demo.py          # datos de demostración
│   └── config.py        # variables de entorno
├── tests/               # 38 pruebas (incluye lectura con una Mongo simulada)
├── Dockerfile · requirements.txt · requirements-dev.txt · .env.example
```
