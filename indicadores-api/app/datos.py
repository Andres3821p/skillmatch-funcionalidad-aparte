"""Capa de datos: lee MongoDB (solo lectura) y lo deja en tablas de pandas.

Reglas de privacidad:
  * De los usuarios se leen UNICAMENTE los nombres de sus habilidades. Nunca
    nombre, correo, telefono ni identificadores: no hay forma de saber de quien es
    una habilidad.
  * Las postulaciones se leen sin carta, hoja de vida ni notas.
"""
from __future__ import annotations

import logging
import threading
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

import pandas as pd

from .config import Config

log = logging.getLogger("indicadores.datos")


class ErrorDatos(Exception):
    """No se pudieron leer los datos (Mongo caido, URI mala, permisos...)."""


def ahora() -> datetime:
    """Hora actual en UTC, sin zona (asi la guarda Spring Data en Mongo)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def clave(texto) -> str:
    """'Bogota', 'bogotá ' y 'BOGOTÁ' son lo mismo: minusculas y sin tildes."""
    t = unicodedata.normalize("NFD", str(texto or "").strip().lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def limpiar_habilidades(valores) -> list[str]:
    """Lista sin vacios ni repetidos (una vez por vacante aunque la escriban dos veces)."""
    vistos: dict[str, str] = {}
    for v in valores or []:
        nombre = str((v.get("name") if isinstance(v, dict) else v) or "").strip()
        if nombre and clave(nombre) not in vistos:
            vistos[clave(nombre)] = nombre
    return list(vistos.values())


@dataclass
class Datos:
    vacantes: pd.DataFrame
    postulaciones: pd.DataFrame
    empresas: pd.DataFrame
    habilidades_usuarios: list[list[str]]  # una lista por persona, SIN identificadores
    fuente: str  # "mongo" | "demo" | "api"
    cargado: datetime
    desactualizado: bool = False
    # Totales de /api/public/stats (solo con la fuente "api"): users, companies, jobs, applications
    totales: dict = field(default_factory=dict)

    @property
    def con_personas(self) -> bool:
        """La API publica no entrega las habilidades de las personas; Mongo y demo si."""
        return self.fuente != "api"

    @property
    def con_postulaciones(self) -> bool:
        """La API publica solo da el TOTAL de postulaciones, no cada una con su estado y fecha."""
        return self.fuente != "api"

    @property
    def abiertas(self) -> pd.DataFrame:
        v = self.vacantes
        return v[v["activa"] & v["estado"].isin(["abierta", ""])]


COLS_VACANTES = ["id", "empresa_id", "titulo", "tipo", "experiencia", "salario_min", "salario_max",
                 "ciudad", "modalidad", "habilidades", "estado", "activa", "publicada"]
COLS_POSTULACIONES = ["id", "vacante_id", "estado", "fecha", "revisada"]
COLS_EMPRESAS = ["id", "nombre", "sector", "ciudad", "activa"]


def _fecha(*valores):
    for v in valores:
        if isinstance(v, datetime):
            return pd.Timestamp(v)
    return pd.NaT


def _ciudad(ubicacion) -> str:
    return str(ubicacion or "").split(",")[0].strip()


def armar_datos(db, fuente: str) -> Datos:
    """Lee las cuatro colecciones de SkillMatch (jobs, applications, companies, users).

    `db` es una base de pymongo (o mongomock en las pruebas). Se piden solo los campos
    necesarios: menos datos viajando y menos informacion personal en memoria.
    """
    vacantes = []
    for j in db.jobs.find({}, {"companyId": 1, "title": 1, "type": 1, "experienceLevel": 1,
                               "salaryMin": 1, "salaryMax": 1, "location": 1, "modality": 1,
                               "skills": 1, "status": 1, "active": 1, "postedDate": 1,
                               "createdAt": 1}):
        vacantes.append({
            "id": str(j["_id"]),
            "empresa_id": str(j.get("companyId") or ""),
            "titulo": j.get("title") or "",
            "tipo": clave(j.get("type")),
            "experiencia": clave(j.get("experienceLevel")),
            "salario_min": j.get("salaryMin"),
            "salario_max": j.get("salaryMax"),
            "ciudad": _ciudad(j.get("location")),
            "modalidad": clave(j.get("modality")),
            "habilidades": limpiar_habilidades(j.get("skills")),
            "estado": clave(j.get("status")),
            "activa": j.get("active") is not False,
            "publicada": _fecha(j.get("postedDate"), j.get("createdAt")),
        })

    postulaciones = []
    for a in db.applications.find({}, {"jobId": 1, "status": 1, "appliedDate": 1,
                                       "reviewedDate": 1, "createdAt": 1}):
        postulaciones.append({
            "id": str(a["_id"]),
            "vacante_id": str(a.get("jobId") or ""),
            "estado": clave(a.get("status")) or "pendiente",
            "fecha": _fecha(a.get("appliedDate"), a.get("createdAt")),
            "revisada": _fecha(a.get("reviewedDate")),
        })

    empresas = []
    for c in db.companies.find({}, {"name": 1, "industry": 1, "location": 1, "active": 1}):
        empresas.append({
            "id": str(c["_id"]),
            "nombre": c.get("name") or "Empresa sin nombre",
            "sector": c.get("industry") or "",
            "ciudad": _ciudad(c.get("location")),
            "activa": c.get("active") is not False,
        })

    personas = [limpiar_habilidades(u.get("skills"))
                for u in db.users.find({"roles": "USER"}, {"skills.name": 1})]

    def tabla(filas, columnas, fechas=()):
        t = pd.DataFrame(filas, columns=columnas)
        for c in fechas:  # con la base vacia la columna nacia sin tipo y .dt fallaba
            t[c] = pd.to_datetime(t[c])
        return t

    return Datos(
        vacantes=tabla(vacantes, COLS_VACANTES, ("publicada",)),
        postulaciones=tabla(postulaciones, COLS_POSTULACIONES, ("fecha", "revisada")),
        empresas=tabla(empresas, COLS_EMPRESAS),
        habilidades_usuarios=personas,
        fuente=fuente,
        cargado=ahora(),
    )


def cargar_desde_mongo(cfg: Config) -> Datos:
    from pymongo import MongoClient  # import tardio: el modo demo no lo necesita

    cliente = MongoClient(cfg.mongodb_uri, serverSelectionTimeoutMS=5000, appname="skillmatch-indicadores")
    try:
        db = cliente[cfg.db_name] if cfg.db_name else cliente.get_default_database(default="skillmatch")
        return armar_datos(db, "mongo")
    finally:
        cliente.close()


def cargar_demo(cfg: Config) -> Datos:
    from .demo import generar_demo
    return generar_demo()


def cargar_desde_api(cfg: Config) -> Datos:
    from .fuente_api import cargar_desde_api as leer
    return leer(cfg)


CARGADORES = {"mongo": cargar_desde_mongo, "api": cargar_desde_api, "demo": cargar_demo}


class Almacen:
    """Guarda los datos en memoria unos minutos para no leer la fuente en cada visita.

    Si la fuente falla pero ya habia datos, sigue sirviendo los ultimos (marcados como
    desactualizados) en lugar de tumbar la pagina; si nunca hubo datos, avisa con ErrorDatos.

    Con la fuente "api" (unas 40 consultas al sitio en vivo) la renovacion va en segundo
    plano: quien visita la pagina recibe al instante los datos que ya habia y, mientras
    tanto, se traen los nuevos.
    """

    def __init__(self, cfg: Config, cargador: Callable[[Config], Datos] | None = None,
                 en_segundo_plano: bool | None = None):
        self.cfg = cfg
        self._cargador = cargador or CARGADORES[cfg.fuente]
        self._fondo = cfg.fuente == "api" if en_segundo_plano is None else en_segundo_plano
        self._datos: Datos | None = None
        self._lock = threading.Lock()
        self._renovando = False

    def _leer(self) -> Datos:
        return self._cargador(self.cfg)

    def _renovar_en_fondo(self):
        try:
            nuevos = self._leer()
            with self._lock:
                self._datos = nuevos
        except Exception as e:  # noqa: BLE001
            log.warning("La fuente %s no respondio (%s); se siguen sirviendo los ultimos datos",
                        self.cfg.fuente, type(e).__name__)
            with self._lock:
                if self._datos is not None:
                    self._datos.desactualizado = True
        finally:
            self._renovando = False

    def precargar(self):
        """Lee la fuente al arrancar, sin bloquear: la primera visita ya encuentra los datos."""
        def tarea():
            try:
                self.obtener()
            except ErrorDatos:
                pass  # se reintenta en la siguiente visita
        threading.Thread(target=tarea, name="precarga-indicadores", daemon=True).start()

    def obtener(self) -> Datos:
        with self._lock:
            vencido = (self._datos is None or
                       (ahora() - self._datos.cargado).total_seconds() > self.cfg.cache_segundos)
            if not vencido:
                return self._datos
            if self._datos is not None and self._fondo:
                if not self._renovando:
                    self._renovando = True
                    threading.Thread(target=self._renovar_en_fondo, daemon=True).start()
                return self._datos
            try:
                self._datos = self._leer()
            except Exception as e:  # noqa: BLE001 - cualquier fallo de red/Mongo
                if self._datos is None:
                    # No se registra la URI ni el detalle: puede llevar la contrasena
                    log.error("No se pudo leer la fuente %s: %s", self.cfg.fuente, type(e).__name__)
                    raise ErrorDatos("No se pudieron leer los datos de SkillMatch") from e
                log.warning("La fuente %s no respondio (%s); se sirven los ultimos datos",
                            self.cfg.fuente, type(e).__name__)
                self._datos.desactualizado = True
            return self._datos
