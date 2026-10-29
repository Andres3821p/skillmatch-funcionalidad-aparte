from datetime import timedelta

import pandas as pd
from bson import ObjectId

from app import indicadores as ind
from tests.conftest import HOY, doc_job


def empresa(nombre, activa=True):
    return {"_id": ObjectId(), "name": nombre, "industry": "Tecnología", "location": "Cartagena", "active": activa}


def persona(*habs):
    return {"roles": ["USER"], "email": "secreto@x.co", "firstName": "Ana",
            "skills": [{"name": h, "level": "AVANZADO"} for h in habs]}


def test_cargador_convierte_ids_estados_y_no_trae_datos_personales(construir):
    e = empresa("Acme")
    d = construir(jobs=[doc_job(e["_id"], ["Java"]), doc_job(e["_id"], ["Java"], estado="CERRADA")],
                  empresas=[e], usuarios=[persona("Java")])
    assert d.vacantes["empresa_id"].iloc[0] == str(e["_id"])
    assert len(d.abiertas) == 1                       # la CERRADA no cuenta como abierta
    assert d.habilidades_usuarios == [["Java"]]        # solo nombres de habilidades
    assert not any("secreto" in str(x) for x in d.habilidades_usuarios)


def test_base_vacia_no_revienta(construir):
    d = construir()
    assert ind.resumen(d)["vacantes_abiertas"] == 0
    assert ind.habilidades_demandadas(d)["items"] == []
    assert ind.empresas_activas(d)["items"] == []
    assert ind.brecha_habilidades(d)["disponible"] is False
    assert ind.embudo_postulaciones(d)["base"] == 0
    assert all(p["valor"] == 0 for p in ind.series(d)["vacantes"])


def test_habilidades_una_vez_por_vacante_y_une_escrituras(construir):
    e = empresa("Acme")
    d = construir(jobs=[doc_job(e["_id"], ["Node.js", "node.js", "Python"]),
                        doc_job(e["_id"], ["node.js"]),
                        doc_job(e["_id"], ["Python"], activa=False)],   # inactiva: no cuenta
                  empresas=[e])
    r = ind.habilidades_demandadas(d)
    assert r["base"] == 2
    assert {i["nombre"].lower(): i["valor"] for i in r["items"]} == {"node.js": 2, "python": 1}
    assert r["items"][0]["porcentaje"] == 100.0


def test_ranking_de_personas_oculta_habilidades_con_menos_de_3(construir):
    d = construir(usuarios=[persona("SQL", "Rara"), persona("SQL"), persona("SQL")])
    nombres = [i["nombre"] for i in ind.habilidades_usuarios(d)["items"]]
    assert nombres == ["SQL"]


def test_empresas_activas_ordena_y_ignora_vacantes_viejas_y_huerfanas(construir):
    a, b = empresa("Alfa"), empresa("Beta")
    jobs = [doc_job(a["_id"], []) for _ in range(3)] + [doc_job(b["_id"], []) for _ in range(2)]
    jobs.append(doc_job(b["_id"], [], dias_atras=200))        # fuera de la ventana de 90 dias
    jobs.append(doc_job(ObjectId(), []))                       # empresa que no existe
    apps = [{"_id": ObjectId(), "jobId": str(jobs[0]["_id"]), "status": "PENDIENTE", "appliedDate": HOY}]
    r = ind.empresas_activas(construir(jobs=jobs, apps=apps, empresas=[a, b]))
    assert [(i["nombre"], i["valor"]) for i in r["items"]] == [("Alfa", 3), ("Beta", 2)]
    assert r["items"][0]["postulaciones"] == 1


def test_brecha_requiere_base_minima_y_marca_lo_que_falta(construir):
    e = empresa("Acme")
    jobs = [doc_job(e["_id"], ["Docker", "SQL"]) for _ in range(12)]
    personas = [persona("SQL") for _ in range(12)]
    d = construir(jobs=jobs, empresas=[e], usuarios=personas)
    r = ind.brecha_habilidades(d)
    assert r["disponible"]
    assert r["faltan"][0]["nombre"] == "Docker" and r["faltan"][0]["brecha"] == 100.0


def test_brecha_no_disponible_con_pocos_datos(construir):
    e = empresa("Acme")
    d = construir(jobs=[doc_job(e["_id"], ["Docker"])], empresas=[e], usuarios=[persona("SQL")])
    assert ind.brecha_habilidades(d)["disponible"] is False


def test_serie_semanal_limites_de_semana_y_parcial():
    # HOY es domingo 18 oct: su semana va del lunes 12 al domingo 18
    fechas = pd.Series(pd.to_datetime([
        "2026-10-11 23:59",   # domingo de la semana anterior
        "2026-10-12 00:00",   # lunes: semana en curso
        "2026-10-18 11:00",   # semana en curso
        "2026-10-25 09:00",   # futuro: se ignora
    ]))
    s = ind.serie_semanal(fechas, HOY, semanas=4)
    assert [p["semana"] for p in s][-2:] == ["2026-10-05", "2026-10-12"]
    assert [p["valor"] for p in s][-2:] == [1, 2]
    assert [p["parcial"] for p in s] == [False, False, False, True]


def test_resumen_tiempo_de_respuesta_y_promedio(construir):
    e = empresa("Acme")
    j = doc_job(e["_id"], [])
    apps = [{"_id": ObjectId(), "jobId": str(j["_id"]), "status": "REVISADA",
             "appliedDate": HOY - timedelta(days=4), "reviewedDate": HOY - timedelta(days=2)},
            {"_id": ObjectId(), "jobId": str(j["_id"]), "status": "PENDIENTE", "appliedDate": HOY}]
    r = ind.resumen(construir(jobs=[j], apps=apps, empresas=[e]))
    assert r["postulaciones_por_vacante"] == 2.0 and r["dias_mediana_respuesta"] == 2.0


def test_salarios_por_experiencia_usa_mediana(construir):
    e = empresa("Acme")
    jobs = [doc_job(e["_id"], [], exp="junior", salario=s) for s in (1e6, 2e6, 9e6)]
    r = ind.salarios_por_experiencia(construir(jobs=jobs, empresas=[e]))
    assert r["items"] == [{"nombre": "Hasta 1 año", "valor": 2_000_000, "vacantes": 3}]
