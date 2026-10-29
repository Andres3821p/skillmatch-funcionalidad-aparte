"""Fuente "api": lee la API PUBLICA del sitio en vivo de SkillMatch.

No necesita la clave de MongoDB ni tocar el proyecto principal: usa las mismas rutas
publicas que usa cualquier visitante del sitio.

  GET /public/stats                 totales: personas, empresas, vacantes, postulaciones
  GET /jobs?page=N&size=50          TODAS las vacantes abiertas, de 50 en 50
  GET /companies?page=N&size=50     empresas (sin correo ni telefono: el backend los oculta)

Lo que la API publica NO entrega (y por eso esos indicadores dicen "no disponible"):
las habilidades de las personas, cada postulacion con su estado y fecha, y las vacantes
ya cerradas. Ver indicadores.py.

Las peticiones salen del SERVIDOR, no del navegador: la politica CORS/CSP del sitio
principal no aplica aqui.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable

from .config import Config
from .datos import Datos, armar_datos

log = logging.getLogger("indicadores.api")

TAMANO_PAGINA = 50          # el maximo que acepta el backend en /jobs
ESPERA_PRIMERA = 90         # segundos: el sitio en Render gratis puede estar dormido
ESPERA_NORMAL = 30
EN_PARALELO = 4             # consultas a la vez: el servidor es gratuito, sin abusar

Pedir = Callable[[str, float], object]


def pedir_json(url: str, espera: float) -> object:
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "skillmatch-indicadores/1.1 (+servicio de indicadores)",
    })
    with urllib.request.urlopen(req, timeout=espera) as r:  # noqa: S310 - URL fija de configuracion
        return json.loads(r.read().decode("utf-8"))


def fecha(valor):
    """'2026-10-20T15:04:05.123' (LocalDateTime de Spring) -> datetime sin zona, en UTC."""
    if not valor or not isinstance(valor, str):
        return None
    texto = valor.strip().replace("Z", "+00:00")
    try:
        f = datetime.fromisoformat(texto)
    except ValueError:
        return None
    if f.tzinfo is not None:
        f = f.astimezone(timezone.utc).replace(tzinfo=None)
    return f


def _contenido(pagina) -> tuple[list, int | None]:
    """Spring puede devolver la pagina plana ({content, totalPages}) o con 'page' aparte."""
    if not isinstance(pagina, dict):
        return [], None
    total = pagina.get("totalPages")
    if total is None and isinstance(pagina.get("page"), dict):
        total = pagina["page"].get("totalPages")
    return list(pagina.get("content") or []), (int(total) if total is not None else None)


class LectorApi:
    def __init__(self, base: str, pedir: Pedir = pedir_json, max_paginas: int = 80):
        self.base = base.rstrip("/")
        self.pedir = pedir
        self.max_paginas = max_paginas

    def url(self, ruta: str, **params) -> str:
        consulta = urllib.parse.urlencode(params)
        return f"{self.base}{ruta}" + (f"?{consulta}" if consulta else "")

    def todas_las_paginas(self, ruta: str, **params) -> list[dict]:
        primera = self.pedir(self.url(ruta, page=0, size=TAMANO_PAGINA, **params), ESPERA_NORMAL)
        filas, total = _contenido(primera)
        if total is None:
            # Sin el total no se sabe cuantas paginas hay: se sigue hasta una pagina corta
            pagina = 1
            ultima = filas
            while len(ultima) == TAMANO_PAGINA and pagina < self.max_paginas:
                ultima, _ = _contenido(self.pedir(self.url(ruta, page=pagina, size=TAMANO_PAGINA, **params),
                                                  ESPERA_NORMAL))
                filas += ultima
                pagina += 1
            return filas
        if total > self.max_paginas:
            log.warning("%s tiene %d paginas; se leen solo %d", ruta, total, self.max_paginas)
        restantes = range(1, min(total, self.max_paginas))
        with ThreadPoolExecutor(max_workers=EN_PARALELO) as hilos:
            paginas = list(hilos.map(
                lambda n: self.pedir(self.url(ruta, page=n, size=TAMANO_PAGINA, **params), ESPERA_NORMAL),
                restantes))
        for p in paginas:
            filas += _contenido(p)[0]
        return filas


class _Coleccion:
    def __init__(self, docs):
        self.docs = docs

    def find(self, filtro=None, proyeccion=None):
        return list(self.docs)


class _Base:
    """Lo minimo de una base de pymongo para reutilizar armar_datos() con lo que llega de la API."""

    def __init__(self, jobs, companies):
        self.jobs, self.companies = _Coleccion(jobs), _Coleccion(companies)
        self.applications, self.users = _Coleccion([]), _Coleccion([])


def a_documento_vacante(j: dict) -> dict:
    return {
        "_id": str(j.get("id") or ""),
        "companyId": j.get("companyId"),
        "title": j.get("title"),
        "type": j.get("type"),
        "experienceLevel": j.get("experienceLevel"),
        "salaryMin": j.get("salaryMin"),
        "salaryMax": j.get("salaryMax"),
        "location": j.get("location"),
        "modality": j.get("modality"),
        "skills": j.get("skills") or [],
        "status": j.get("status") or "abierta",   # /jobs solo devuelve vacantes abiertas
        "active": j.get("active"),
        "postedDate": fecha(j.get("postedDate")),
        "createdAt": fecha(j.get("createdAt")),
    }


def a_documento_empresa(c: dict) -> dict:
    return {"_id": str(c.get("id") or ""), "name": c.get("name"), "industry": c.get("industry"),
            "location": c.get("location"), "active": c.get("active")}


def cargar_desde_api(cfg: Config, pedir: Pedir = pedir_json) -> Datos:
    lector = LectorApi(cfg.skillmatch_api, pedir, cfg.max_paginas)
    # La primera consulta despierta al sitio si estaba dormido (Render gratis): espera larga
    stats = pedir(lector.url("/public/stats"), ESPERA_PRIMERA)
    if not isinstance(stats, dict):
        raise ValueError("La API de SkillMatch no devolvio las cifras esperadas")
    vacantes = [a_documento_vacante(j) for j in lector.todas_las_paginas("/jobs", sortBy="postedDate",
                                                                          direction="desc")]
    empresas = [a_documento_empresa(c) for c in lector.todas_las_paginas("/companies")]
    datos = armar_datos(_Base(vacantes, empresas), "api")
    datos.totales = {k: int(v) for k, v in stats.items() if isinstance(v, (int, float))}
    log.info("API de SkillMatch: %d vacantes abiertas y %d empresas leidas", len(vacantes), len(empresas))
    return datos
