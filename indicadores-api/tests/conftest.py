import os
import sys
from datetime import datetime

import mongomock
import pytest
from bson import ObjectId

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.datos import armar_datos  # noqa: E402

HOY = datetime(2026, 10, 18, 12, 0)  # un domingo


def doc_job(empresa, habilidades, dias_atras=5, estado="ABIERTA", activa=True, tipo="empleo",
            exp="junior", salario=2_000_000.0, ciudad="Cartagena"):
    from datetime import timedelta
    return {"_id": ObjectId(), "companyId": str(empresa), "title": "Dev", "type": tipo,
            "experienceLevel": exp, "salaryMin": salario, "salaryMax": salario + 1e6,
            "location": ciudad, "modality": "remoto", "skills": habilidades, "status": estado,
            "active": activa, "postedDate": HOY - timedelta(days=dias_atras)}


@pytest.fixture
def base_vacia():
    return mongomock.MongoClient().db


@pytest.fixture
def construir(base_vacia):
    """Devuelve una funcion que arma Datos a partir de documentos con la forma del backend."""
    def _construir(jobs=(), apps=(), empresas=(), usuarios=()):
        db = base_vacia
        for nombre, docs in (("jobs", jobs), ("applications", apps), ("companies", empresas), ("users", usuarios)):
            if docs:
                db[nombre].insert_many(list(docs))
        d = armar_datos(db, "mongo")
        d.cargado = HOY
        return d
    return _construir
