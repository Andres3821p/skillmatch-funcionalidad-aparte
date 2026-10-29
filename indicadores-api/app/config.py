"""Configuracion del servicio: todo sale de variables de entorno (nada de secretos en el codigo).

De donde salen los datos (FUENTE), en este orden si no se dice explicitamente:
  1. "mongo": si hay MONGODB_URI. Lee la base de SkillMatch (solo lectura). Es la mas completa.
  2. "demo":  si MODO_DEMO=1. Datos inventados para probar sin internet.
  3. "api":   en cualquier otro caso. Lee la API PUBLICA del sitio en vivo
              (https://skillmatch-yz37.onrender.com/api): vacantes abiertas, empresas y
              totales. No necesita ninguna clave.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

FUENTES = ("mongo", "api", "demo")
API_SKILLMATCH = "https://skillmatch-yz37.onrender.com/api"


def _lista(valor: str) -> list[str]:
    return [v.strip().rstrip("/") for v in valor.split(",") if v.strip()]


def _entero(nombre: str, defecto: int) -> int:
    try:
        return int(os.getenv(nombre, "") or defecto)
    except ValueError:
        return defecto


@dataclass(frozen=True)
class Config:
    mongodb_uri: str
    db_name: str
    fuente: str               # "mongo" | "api" | "demo"
    skillmatch_api: str       # base de la API publica, sin "/" al final
    cache_segundos: int
    origenes: list[str]
    max_paginas: int = 80     # tope de paginas de 50 vacantes que se leen de la API (4.000)

    @property
    def modo_demo(self) -> bool:
        return self.fuente == "demo"


def elegir_fuente(uri: str, demo: str, explicita: str) -> str:
    explicita = explicita.strip().lower()
    if explicita in FUENTES:
        if explicita == "mongo" and not uri:
            return "api"  # pidieron Mongo sin URI: no hay de donde leer
        return explicita
    if demo.strip() == "1":
        return "demo"
    return "mongo" if uri else "api"


def cargar_config() -> Config:
    uri = os.getenv("MONGODB_URI", "").strip()
    fuente = elegir_fuente(uri, os.getenv("MODO_DEMO", ""), os.getenv("FUENTE", ""))
    # Leer la API son ~40 consultas: se guarda mas tiempo que una lectura de Mongo
    cache = _entero("CACHE_SEGUNDOS", 900 if fuente == "api" else 300)
    return Config(
        mongodb_uri=uri,
        db_name=os.getenv("DB_NAME", "").strip(),
        fuente=fuente,
        skillmatch_api=(os.getenv("SKILLMATCH_API", "").strip() or API_SKILLMATCH).rstrip("/"),
        cache_segundos=cache,
        origenes=_lista(os.getenv("ALLOWED_ORIGINS", "")),
        max_paginas=_entero("MAX_PAGINAS", 80),
    )
