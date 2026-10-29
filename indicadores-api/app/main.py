"""API de indicadores de SkillMatch (solo lectura, publica, sin datos personales).

Cada indicador es su propio endpoint: si uno falla, la pagina muestra "No se pudo cargar
este indicador. Reintentar" solo en esa tarjeta y las demas siguen funcionando.

Arranque local:   uvicorn app.main:app --reload --port 8000
Documentacion:    http://localhost:8000/docs
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import indicadores as ind
from . import prediccion as pred
from .config import cargar_config
from .datos import Almacen, ErrorDatos

logging.basicConfig(level=logging.INFO)

cfg = cargar_config()
almacen = Almacen(cfg)

app = FastAPI(
    title="SkillMatch · Indicadores y pronóstico",
    description="Indicadores del mercado laboral de Cartagena y un modelo predictivo, "
                "calculados con los datos de SkillMatch. Solo lectura; no expone datos personales.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.origenes,
    # Cualquier puerto de localhost (Live Server usa 5500 o 5501)
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.exception_handler(ErrorDatos)
async def _sin_datos(_: Request, e: ErrorDatos):
    return JSONResponse(status_code=503, content={"detail": str(e)})


def _datos():
    return almacen.obtener()


def _cache(r: Response):
    # El navegador y los proxies reutilizan la respuesta un minuto
    r.headers["Cache-Control"] = "public, max-age=60"


PREFIJO = "/api/indicadores"


@app.get("/")
def raiz():
    return {"servicio": "SkillMatch indicadores", "documentacion": "/docs", "salud": f"{PREFIJO}/salud"}


@app.get(f"{PREFIJO}/salud")
def salud():
    """Para el health check del hosting. No toca la base de datos."""
    return {"estado": "ok", "fuente": "demo" if cfg.modo_demo else "mongo"}


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
    s = ind.series(_datos())[serie]
    return pred.pronostico_semanal(s, semanas, unidad=serie)


@app.get(f"{PREFIJO}/tendencia-habilidades")
def tendencia_habilidades(r: Response, top: int = Query(6, ge=1, le=15)):
    """Habilidades que suben o bajan en las vacantes (con control de falsos positivos)."""
    _cache(r)
    return pred.tendencia_habilidades(_datos(), top=top)
