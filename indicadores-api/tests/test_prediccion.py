from datetime import date, datetime, timedelta

import numpy as np
import pytest
from bson import ObjectId

from app import prediccion as pred
from app.datos import armar_datos
from tests.conftest import HOY


def serie(valores, parcial_final=False, inicio=date(2026, 1, 5)):
    return [{"semana": (inicio + timedelta(weeks=i)).isoformat(), "valor": v,
             "parcial": parcial_final and i == len(valores) - 1} for i, v in enumerate(valores)]


def test_crecimiento_lineal_se_pronostica_hacia_arriba():
    r = pred.pronostico_semanal(serie(list(range(10, 34))), 4)
    assert r["disponible"] and r["tendencia"] == "sube"
    assert r["modelo"] in ("lineal", "holt")
    assert r["evaluacion"]["mejora_pct"] > 30
    assert r["pronostico"][0]["valor"] > 30


def test_serie_constante_queda_estable_con_el_promedio():
    r = pred.pronostico_semanal(serie([12] * 16), 4)
    assert r["modelo"] == "promedio" and r["tendencia"] == "estable"
    assert all(p["valor"] == 12 for p in r["pronostico"])


def test_con_ruido_puro_no_presume_mejora():
    rng = np.random.default_rng(7)
    r = pred.pronostico_semanal(serie([int(v) for v in rng.poisson(15, 30)]), 4)
    assert r["evaluacion"]["mejora_pct"] < 15
    assert "referencia" in r["lectura"] or "menos que el promedio" in r["lectura"]


def test_pocas_semanas_no_pronostica():
    r = pred.pronostico_semanal(serie([5, 6, 7, 8, 9]), 4)
    assert r["disponible"] is False and "8 semanas" in r["motivo"]


def test_ceros_iniciales_no_cuentan_como_historia():
    r = pred.pronostico_semanal(serie([0] * 10 + [9, 10, 11, 10, 12]), 4)  # solo 5 semanas reales
    assert r["disponible"] is False


def test_la_semana_parcial_no_entrena_el_modelo():
    completas = [10] * 14
    con_parcial = pred.pronostico_semanal(serie(completas + [1], parcial_final=True), 4)
    sin_parcial = pred.pronostico_semanal(serie(completas), 4)
    assert con_parcial["pronostico"] == sin_parcial["pronostico"] or \
        con_parcial["pronostico"][0]["valor"] == sin_parcial["pronostico"][0]["valor"]
    assert con_parcial["pronostico"][0]["en_curso"] is True    # el primer punto es la semana en curso


def test_intervalos_validos_y_crecen_con_el_horizonte():
    rng = np.random.default_rng(3)
    r = pred.pronostico_semanal(serie([int(v) for v in rng.poisson(8, 24)]), 6)
    anchos = [p["maximo"] - p["minimo"] for p in r["pronostico"]]
    assert all(p["minimo"] >= 0 and p["minimo"] <= p["valor"] <= p["maximo"] for p in r["pronostico"])
    assert anchos[-1] > anchos[0]


def test_benjamini_hochberg_controla_falsos_positivos():
    # 1 p-valor muy chico entre 20 casi-uniformes: solo ese sobrevive
    p = [0.0001] + [0.04 + 0.04 * i for i in range(19)]
    ok = pred._benjamini_hochberg(p)
    assert ok[0] and sum(ok) == 1


def _datos_con_publicaciones(construir_jobs):
    from app.datos import armar_datos
    import mongomock
    db = mongomock.MongoClient().db
    db.jobs.insert_many(construir_jobs)
    d = armar_datos(db, "mongo")
    d.cargado = HOY
    return d


def _job(habs, lunes_semana, i):
    return {"_id": ObjectId(), "companyId": "x", "skills": habs, "status": "ABIERTA", "active": True,
            "postedDate": lunes_semana + timedelta(hours=i % 100)}


def test_detecta_una_habilidad_que_sube_de_verdad_y_no_inventa_otras():
    rng = np.random.default_rng(11)
    jobs = []
    actual = datetime(2026, 10, 12)           # lunes de la semana en curso
    for w in range(12):                        # 12 semanas completas hacia atras
        lunes = actual - timedelta(weeks=12 - w)
        p_docker = 0.10 + 0.05 * w             # sube de 10 % a 65 %
        for i in range(60):
            habs = ["Docker"] if rng.random() < p_docker else []
            habs += ["SQL"] if rng.random() < 0.40 else []   # estable
            habs += ["Git"] if rng.random() < 0.30 else []   # estable
            jobs.append(_job(habs, lunes, i))
    r = pred.tendencia_habilidades(_datos_con_publicaciones(jobs), HOY)
    assert r["disponible"]
    assert r["suben"][0]["nombre"] == "Docker" and r["suben"][0]["evidencia"] == "firme"
    firmes = [x["nombre"] for x in r["suben"] + r["bajan"] if x["evidencia"] == "firme"]
    assert firmes == ["Docker"]
    # La mini-línea: un porcentaje por semana analizada, y Docker termina más arriba de donde empezó
    docker = r["suben"][0]["serie"]
    assert len(docker) == r["semanas_analizadas"]
    assert all(0 <= v <= 100 for v in docker)
    assert docker[-1] > docker[0]


def test_tendencias_no_disponibles_con_pocas_semanas():
    actual = datetime(2026, 10, 12)
    jobs = [_job(["A"], actual - timedelta(weeks=1), i) for i in range(30)]
    assert pred.tendencia_habilidades(_datos_con_publicaciones(jobs), HOY)["disponible"] is False
