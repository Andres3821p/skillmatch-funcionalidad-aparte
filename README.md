# SkillMatch · Tendencias y pronóstico (funcionalidad aparte)

Un servicio aparte de [SkillMatch](https://skillmatch-yz37.onrender.com) que calcula **indicadores del mercado
laboral** y un **pronóstico de vacantes**, y los muestra en una página con el mismo diseño del sitio.

**Funciona con los datos en vivo de SkillMatch sin ninguna clave**: lee la misma API pública que usa cualquier
visitante del sitio (vacantes abiertas, empresas y totales). No toca el proyecto principal.

```
                         ┌──────────── Render (servicio aparte, gratis) ────────────┐
Navegador ──HTTPS──▶     │  indicadores-api (Python + FastAPI)                       │
                         │   ├── /            la página de tendencias (carpeta web/) │
                         │   └── /api/indicadores/...  indicadores y pronóstico      │
                         └──────────────────────┬───────────────────────────────────┘
                                                │ lee cada 15 min (solo GET públicos)
                                                ▼
                         SkillMatch en vivo: skillmatch-yz37.onrender.com/api
                           /public/stats · /jobs · /companies
```

## Por qué así

Revisando el [repositorio principal](https://github.com/jesuscastilla-cloud/Skillmatch):

1. El sitio sirve páginas y API desde **un solo servicio**, con una política de seguridad que solo deja a sus
   páginas pedir datos a su propio dominio (`connect-src 'self'` en `SecurityConfig.java`). Una página del sitio
   no puede llamar a un servicio externo sin cambiar el backend.
2. La clave de MongoDB (`MONGODB_URI`) vive en el Render del proyecto principal.
3. La API pública sí entrega, sin clave, todas las vacantes abiertas con sus habilidades, fechas, salarios y
   empresas, más los totales del sitio.

Por eso este servicio lee esa API **desde el servidor** (ahí no aplican CORS ni la política del navegador) y
sirve su propia página en el mismo dominio. Resultado: funciona hoy, con datos reales y sin pedirle nada a nadie.

## Qué muestra según la fuente de datos

| Indicador | API pública (por defecto) | MongoDB de solo lectura |
|---|:-:|:-:|
| Vacantes abiertas, empresas activas, personas, postulaciones por vacante | Sí | Sí |
| Habilidades más pedidas por las empresas | Sí | Sí |
| Empresas más activas (90 días) | Sí, sin postulaciones por empresa | Sí |
| Salario típico según la experiencia | Sí | Sí |
| **Pronóstico de vacantes por semana** (modelo 1) | Sí, solo con vacantes que siguen abiertas | Sí |
| **Habilidades que suben o bajan** (modelo 2) | Sí | Sí |
| Habilidades de las personas y brecha oferta/demanda | No (dato privado) | Sí |
| Estado de las postulaciones, pronóstico de postulaciones, días en responder | No (dato privado) | Sí |

Lo que no está disponible aparece en la página con su motivo, nunca con ceros o cifras inventadas.

La fuente se elige sola: si existe `MONGODB_URI` usa Mongo; si `MODO_DEMO=1`, datos inventados; si no, la API
pública. También se puede forzar con `FUENTE=api|mongo|demo`.

## Probarlo en tu PC (Windows)

Necesitas [Python 3.11 o superior](https://www.python.org/downloads/) (marca *Add python.exe to PATH* al
instalarlo).

```powershell
cd indicadores-api
.\iniciar.ps1          # datos en vivo de SkillMatch  ->  abre http://localhost:8000
.\iniciar.ps1 -Demo    # datos inventados, sin internet
```

Si PowerShell dice que no se pueden ejecutar scripts:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (una sola vez) y vuelve a intentar.

Pruebas: `.\.venv\Scripts\python -m pytest` (57 pruebas, no necesitan internet).

## Publicarlo en Render

El archivo `render.yaml` ya trae todo. En Render: **New → Blueprint → este repositorio → Apply**. No hay que
escribir ninguna variable. Cada `git push` a `main` vuelve a publicar.

En el plan gratuito el servicio se duerme tras 15 minutos sin visitas; la primera visita tarda hasta un par de
minutos (si el sitio de SkillMatch también estaba dormido) y la página muestra un aviso mientras tanto.

## Estructura

```
indicadores-api/
├── app/
│   ├── main.py          endpoints, cabeceras de seguridad y la página en /
│   ├── config.py        variables de entorno y elección de la fuente
│   ├── fuente_api.py    lectura de la API pública de SkillMatch
│   ├── datos.py         lectura de MongoDB (solo lectura), caché y renovación en segundo plano
│   ├── indicadores.py   cálculo de indicadores (funciones puras)
│   ├── prediccion.py    los dos modelos predictivos
│   └── demo.py          datos de demostración
├── web/                 la página: index.html + assets (app.css es el del sitio principal)
├── tests/               57 pruebas (API de SkillMatch y MongoDB simuladas)
└── Dockerfile · requirements.txt · iniciar.ps1 · .env.example
render.yaml              despliegue en Render
```

Detalles de los modelos y de cada endpoint: [indicadores-api/README.md](indicadores-api/README.md).

## Más adelante: dentro del sitio principal

Para que la página viva en el propio dominio de SkillMatch hace falta un PR al repositorio principal que:
1. agregue la dirección de este servicio a `connect-src` en `SecurityConfig.java`;
2. copie `web/index.html` como `pages/tendencias.html` y sus archivos de `web/assets/`, usando `api-config.js`
   en lugar de `base.js` y poniendo la dirección del servicio en `window.SKILLMATCH_INDICADORES_API`;
3. ponga un enlace en `dashboard.html`.

Mientras tanto, basta con un enlace desde el sitio a la dirección de Render de este servicio.
