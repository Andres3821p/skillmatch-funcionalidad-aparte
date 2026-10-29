"""Configuracion del servicio: todo sale de variables de entorno (nada de secretos en el codigo)."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _lista(valor: str) -> list[str]:
    return [v.strip().rstrip("/") for v in valor.split(",") if v.strip()]


@dataclass(frozen=True)
class Config:
    mongodb_uri: str
    db_name: str
    modo_demo: bool
    cache_segundos: int
    origenes: list[str]


def cargar_config() -> Config:
    uri = os.getenv("MONGODB_URI", "").strip()
    return Config(
        mongodb_uri=uri,
        db_name=os.getenv("DB_NAME", "").strip(),
        # Sin URI no hay de donde leer: se pasa a demostracion, y la API lo avisa en /salud
        modo_demo=os.getenv("MODO_DEMO", "").strip() == "1" or not uri,
        cache_segundos=int(os.getenv("CACHE_SEGUNDOS", "300") or 300),
        origenes=_lista(os.getenv("ALLOWED_ORIGINS", "")),
    )
