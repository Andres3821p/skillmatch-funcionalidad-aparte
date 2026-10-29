"""API de indicadores de SkillMatch (solo lectura, publica, sin datos personales).

Cada indicador es su propio endpoint: si uno falla, la pagina muestra "No se pudo cargar
este indicador. Reintentar" solo en esa tarjeta y las demas siguen funcionando.

El mismo servicio sirve la pagina (carpeta web/) en la raiz: pagina y API quedan en el
mismo dominio, asi que no hay CORS ni politicas de seguridad que ajustar.

Arranque local:   uvicorn app.main:app --reload --port 8000   ->  http://localhost:8000
Documentacion:    http://localhost:8000/docs
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import indicadores as ind
from . import prediccion as pred
from .config import cargar_config
from .datos import Almacen, ErrorDatos

logging.basicConfig(level=logging.INFO)

cfg = cargar_config()
almacen = Almacen(cfg)
WEB = Path(__file__).resolve().parent.parent / "web"
logging.getLogger("indicadores").info("Fuente de datos: %s", cfg.fuente)


@asynccontextmanager
async def _arranque(_app: FastAPI):
    # Lee la fuente apenas arranca, sin bloquear: la primera visita ya encuentra los datos
    if os.getenv("PRECARGAR", "1") != "0":
        almacen.precargar()
    yield


app = FastAPI(
    title="SkillMatch · Indicadores y pronóstico",
    description="Indicadores del mercado laboral de Cartagena y un modelo predictivo, "
                "calculados con los datos de SkillMatch. Solo lectura; no expone datos personales.",
    version="1.1.0",
    lifespan=_arranque,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.origenes,
    # Cualquier puerto de localhost (Live Server usa 5500 o 5501)
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["GET"],
    allow_headers=["*"],
)


# Las mismas protecciones que el sitio principal (SecurityConfig.java): la pagina solo
# habla con su propio servidor y no se puede incrustar en otro sitio.
CABECERAS = {
    "Content-Security-Policy": ("default-src 'self'; script-src 'self'; "
                                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                                "font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data:; "
                                "connect-src 'self'; frame-ancestors 'self'"),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "SAMEORIGIN",
}


@app.middleware("http")
async def _cabeceras(request: Request, call_next):
    respuesta = await call_next(request)
    if not request.url.path.startswith(("/docs", "/redoc")):  # Swagger usa scripts de un CDN
        for k, v in CABECERAS.items():
            respuesta.headers.setdefault(k, v)
    return respuesta


@app.exception_handler(ErrorDatos)
async def _sin_datos(_: Request, e: ErrorDatos):
    return JSONResponse(status_code=503, content={"detail": str(e)})


def _datos():
    return almacen.obtener()


def _cache(r: Response):
    # El navegador y los proxies reutilizan la respuesta un minuto
    r.headers["Cache-Control"] = "public, max-age=60"


PREFIJO = "/api/indicadores"


@app.get(PREFIJO)
def informacion():
    return {"servicio": "SkillMatch indicadores", "version": app.version, "fuente": cfg.fuente,
            "documentacion": "/docs", "salud": f"{PREFIJO}/salud", "pagina": "/"}


@app.get(f"{PREFIJO}/salud")
def salud():
    """Para el health check del hosting. No toca la fuente de datos."""
    return {"estado": "ok", "fuente": cfg.fuente}


@app.get(f"{PREFIJO}/resumen")
def resumen(r: Response):
    _cache(r)
    return ind.resumen(_datos())


@app.get(f"{PREFIJO}/habilidades-demandadas")
def habilidades_demandadas(r: Response, top: int = Query(10, ge=1, le=30)):
    """Habilidades más pedidas en las vacantes abiertas."""
    _cache(r)
    return ind.habilidades_demandadas(_datos(), top)


@app.get(f"{PREFIJO}/empresas-activas")
def empresas_activas(r: Response, top: int = Query(10, ge=1, le=30)):
    """Empresas con más vacantes publicadas en los últimos 90 días."""
    _cache(r)
    return ind.empresas_activas(_datos(), top)


@app.get(f"{PREFIJO}/habilidades-usuarios")
def habilidades_usuarios(r: Response, top: int = Query(10, ge=1, le=30)):
    """Habilidades más frecuentes entre las personas registradas (solo agregados)."""
    _cache(r)
    return ind.habilidades_usuarios(_datos(), top)


@app.get(f"{PREFIJO}/brecha-habilidades")
def brecha_habilidades(r: Response, top: int = Query(5, ge=1, le=15)):
    """Qué piden las empresas y cuántas personas lo tienen."""
    _cache(r)
    return ind.brecha_habilidades(_datos(), top)


@app.get(f"{PREFIJO}/salarios")
def salarios(r: Response):
    _cache(r)
    return ind.salarios_por_experiencia(_datos())


@app.get(f"{PREFIJO}/postulaciones-estado")
def postulaciones_estado(r: Response):
    _cache(r)
    return ind.embudo_postulaciones(_datos())


@app.get(f"{PREFIJO}/series")
def series(r: Response, semanas: int = Query(26, ge=8, le=104)):
    """Vacantes publicadas y postulaciones recibidas por semana."""
    _cache(r)
    return ind.series(_datos(), semanas=semanas)


@app.get(PREFIJO + "/pronostico/{serie}")
def pronostico(serie: str, r: Response, semanas: int = Query(4, ge=1, le=8)):
    """Pronóstico semanal. `serie` = vacantes | postulaciones."""
    if serie not in ("vacantes", "postulaciones"):
        raise HTTPException(404, "Serie desconocida: usa 'vacantes' o 'postulaciones'")
    _cache(r)
    d = _datos()
    if serie == "postulaciones" and not d.con_postulaciones:
        return {"disponible": False, "unidad": serie, "motivo": ind.MOTIVO_POSTULACIONES}
    s = ind.series(d)
    resultado = pred.pronostico_semanal(s[serie], semanas, unidad=serie)
    if s.get("nota") and resultado.get("disponible"):
        resultado["nota"] = s["nota"]
    return resultado


@app.get(f"{PREFIJO}/tendencia-habilidades")
def tendencia_habilidades(r: Response, top: int = Query(6, ge=1, le=15)):
    """Habilidades que suben o bajan en las vacantes (con control de falsos positivos)."""
    _cache(r)
    return pred.tendencia_habilidades(_datos(), top=top)


# La pagina va al final: las rutas /api/... de arriba tienen prioridad
if WEB.is_dir():
    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
