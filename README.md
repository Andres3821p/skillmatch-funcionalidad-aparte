# SkillMatch · Indicadores y pronóstico (funcionalidad aparte)

Funcionalidad adicional para SkillMatch: un servicio aparte (Python + FastAPI) que lee la base de
datos de SkillMatch en modo solo lectura, calcula indicadores del mercado laboral y entrena dos
modelos predictivos sencillos. La página `tendencias.html` la consume por HTTP con el mismo diseño
del sitio.

```
MongoDB Atlas ──(solo lectura)──▶ indicadores-api (FastAPI) ──JSON──▶ tendencias.html
       ▲
       └── backend Java (Spring Boot): no se toca
```

## Carpetas

| Carpeta | Qué contiene |
|---|---|
| `indicadores-api/` | El servicio: endpoints, cálculo de indicadores, modelos, pruebas y Dockerfile. Detalles en su [README](indicadores-api/README.md). |
| `SkillMatch/src/pages/` | `tendencias.html` (página nueva) y `dashboard.html` (con el enlace a la nueva). |
| `SkillMatch/src/assets/js/` | `tendencias.js`, `indicadores-config.js` (dirección del servicio) e `indicadores.js` (del dashboard). |
| `SkillMatch/src/assets/css/` | `tendencias.css` (solo usa los tokens de `app.css`) y `app.css` del proyecto. |

Los archivos `api-config.js`, `ui.js`, las imágenes y las demás páginas son del proyecto principal
SkillMatch: esta carpeta solo trae lo nuevo o lo que cambia.

## Probarlo rápido (Windows)

```powershell
cd indicadores-api
.\iniciar.ps1          # datos de demostración en http://localhost:8000
```

Luego abre `SkillMatch/src/pages/tendencias.html` con Live Server, dentro del proyecto
SkillMatch completo (necesita `api-config.js` y `ui.js`).

Pruebas: `cd indicadores-api; .venv\Scripts\python -m pytest` (38 pruebas).

## Pendiente

- Cambiar `API_INDICADORES` en `indicadores-config.js` por la dirección real cuando se despliegue.
- `indicadores-inicio.js` (franja de indicadores en la portada): `tendencias.css` ya trae sus estilos,
  pero el script aún no existe.
