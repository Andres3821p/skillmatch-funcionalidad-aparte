"""Pruebas de la fuente "api": lee la API publica del sitio en vivo, aqui simulada con
respuestas que tienen la misma forma que las de Spring Boot (JobResponse, CompanyResponse,
Page y /public/stats)."""
import importlib
import threading
import time
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import indicadores as ind
from app import prediccion as pred
from app.config import Config, elegir_fuente
from app.datos import Almacen
from app.fuente_api import LectorApi, cargar_desde_api, fecha

BASE = "https://skillmatch.example/api"
HOY = datetime(2026, 10, 18, 12, 0)


def _cfg(**cambios):
    datos = dict(mongodb_uri="", db_name="", fuente="api", skillmatch_api=BASE,
                 cache_segundos=900, origenes=[], max_paginas=80)
    datos.update(cambios)
    return Config(**datos)


def sitio_falso(n_semanas=16, por_semana=15, plana=True, semilla=5):
    """Devuelve una funcion pedir(url, espera) que imita la API de SkillMatch."""
    rng = np.random.default_rng(semilla)
    empresas = [{"id": f"c{i}", "name": f"Empresa {i}", "industry": "Tecnología", "location": "Cartagena",
                 "email": None, "phone": None, "active": True} for i in range(6)]
    vacantes = []
    for s in range(n_semanas):
        for k in range(por_semana):
            publicada = HOY - timedelta(weeks=n_semanas - s, hours=int(rng.integers(0, 150)))
            vacantes.append({
                "id": f"j{s}-{k}", "companyId": f"c{k % 6}", "companyName": f"Empresa {k % 6}",
                "title": "Desarrollador", "type": "empleo", "experienceLevel": "junior",
                "salaryMin": 2_000_000.0 + 100_000 * (k % 3), "salaryMax": 3_000_000.0,
                "location": "Cartagena, Bolívar", "modality": "remoto",
                "skills": ["Java", "SQL"] + (["Docker"] if rng.random() < 0.1 + 0.04 * s else []),
                "status": "abierta", "active": True,
                # Spring escribe LocalDateTime asi: sin zona y con microsegundos
                "postedDate": publicada.strftime("%Y-%m-%dT%H:%M:%S.%f"),
                "createdAt": publicada.isoformat(),
            })
    vacantes.sort(key=lambda v: v["postedDate"], reverse=True)
    llamadas = []

    def pagina(lista, q):
        n, size = int(q.get("page", ["0"])[0]), int(q.get("size", ["20"])[0])
        trozo = lista[n * size:(n + 1) * size]
        total = max(1, -(-len(lista) // size))
        if plana:
            return {"content": trozo, "totalElements": len(lista), "totalPages": total,
                    "number": n, "size": size, "last": n >= total - 1}
        return {"content": trozo, "page": {"size": size, "number": n, "totalElements": len(lista),
                                           "totalPages": total}}

    def pedir(url, espera):
        u = urlparse(url)
        q = parse_qs(u.query)
        llamadas.append((u.path, espera))
        if u.path.endswith("/public/stats"):
            return {"users": 150, "companies": 6, "jobs": len(vacantes), "applications": 640}
        if u.path.endswith("/jobs"):
            assert int(q["size"][0]) <= 50  # el backend no acepta mas
            return pagina(vacantes, q)
        if u.path.endswith("/companies"):
            return pagina(empresas, q)
        raise AssertionError("ruta inesperada " + url)

    pedir.llamadas = llamadas
    pedir.vacantes = vacantes
    return pedir


def _datos(**kw):
    pedir = sitio_falso(**kw)
    d = cargar_desde_api(_cfg(), pedir)
    d.cargado = HOY
    return d, pedir


# ---------------------------------------------------------------- lectura

def test_lee_todas_las_paginas_y_arma_los_datos():
    d, pedir = _datos()
    assert d.fuente == "api"
    assert len(d.vacantes) == len(pedir.vacantes) == 240        # 5 paginas de 50
    assert len(d.abiertas) == 240                                # status "abierta" en minusculas
    assert len(d.empresas) == 6
    assert d.totales == {"users": 150, "companies": 6, "jobs": 240, "applications": 640}
    assert d.vacantes["publicada"].notna().all()
    assert d.vacantes["ciudad"].iloc[0] == "Cartagena"
    # La primera consulta espera mas: el sitio puede estar dormido
    assert pedir.llamadas[0] == ("/api/public/stats", 90)


def test_tambien_entiende_la_pagina_con_page_aparte():
    d, _ = _datos(plana=False)
    assert len(d.vacantes) == 240


def test_sin_total_de_paginas_sigue_hasta_una_pagina_corta():
    filas = [{"id": i} for i in range(120)]

    def pedir(url, espera):
        n = int(parse_qs(urlparse(url).query)["page"][0])
        return {"content": filas[n * 50:(n + 1) * 50]}
    assert len(LectorApi(BASE, pedir).todas_las_paginas("/jobs")) == 120


def test_respeta_el_tope_de_paginas():
    pedir = sitio_falso()
    lector = LectorApi(BASE, pedir, max_paginas=2)
    assert len(lector.todas_las_paginas("/jobs")) == 100


def test_fechas_de_spring():
    assert fecha("2026-10-20T15:04:05.123456") == datetime(2026, 10, 20, 15, 4, 5, 123456)
    assert fecha("2026-10-20T15:04:05Z") == datetime(2026, 10, 20, 15, 4, 5)
    assert fecha("2026-10-20T10:04:05-05:00") == datetime(2026, 10, 20, 15, 4, 5)
    assert fecha(None) is None and fecha("mañana") is None


def test_si_la_api_responde_algo_raro_falla_con_error():
    with pytest.raises(ValueError):
        cargar_desde_api(_cfg(), lambda url, espera: "<html>error</html>")


# ---------------------------------------------------------------- indicadores con la fuente api

def test_indicadores_que_si_se_pueden_calcular():
    d, _ = _datos()
    dem = ind.habilidades_demandadas(d)
    assert dem["base"] == 240 and dem["items"][0]["nombre"] in ("Java", "SQL")
    emp = ind.empresas_activas(d)
    assert emp["items"] and all(i["postulaciones"] is None for i in emp["items"])
    assert ind.salarios_por_experiencia(d)["items"][0]["nombre"] == "Hasta 1 año"
    r = ind.resumen(d)
    assert r["fuente"] == "api" and r["personas"] == 150 and r["postulaciones"] == 640
    assert r["empresas_activas"] == 6
    assert r["postulaciones_por_vacante"] == round(640 / 240, 1)
    assert r["dias_mediana_respuesta"] is None


def test_lo_que_la_api_publica_no_permite_se_dice_claro():
    d, _ = _datos()
    for resultado in (ind.habilidades_usuarios(d), ind.brecha_habilidades(d), ind.embudo_postulaciones(d)):
        assert resultado["disponible"] is False and "API pública" in resultado["motivo"]
    s = ind.series(d)
    assert s["postulaciones"] == [] and "abiertas" in s["nota"]


def test_pronostico_y_tendencias_funcionan_con_los_datos_de_la_api():
    d, _ = _datos()
    p = pred.pronostico_semanal(ind.series(d)["vacantes"], 4)
    assert p["disponible"] and len(p["pronostico"]) == 4
    t = pred.tendencia_habilidades(d)
    assert t["disponible"] and t["vacantes_analizadas"] > 0
    assert any(x["nombre"] == "Docker" for x in t["suben"])


def test_mongo_y_demo_siguen_teniendo_todo():
    from app.demo import generar_demo
    d = generar_demo()
    assert d.con_personas and d.con_postulaciones
    assert ind.habilidades_usuarios(d)["disponible"] is True


# ---------------------------------------------------------------- configuracion

@pytest.mark.parametrize("uri, demo, explicita, esperado", [
    ("", "", "", "api"),                       # sin nada: el sitio en vivo
    ("mongodb+srv://x", "", "", "mongo"),
    ("mongodb+srv://x", "1", "", "demo"),       # MODO_DEMO manda sobre la URI
    ("", "", "mongo", "api"),                   # pidieron mongo sin URI: no hay de donde leer
    ("mongodb+srv://x", "", "API", "api"),
    ("", "1", "api", "api"),                    # FUENTE manda sobre todo
])
def test_elegir_fuente(uri, demo, explicita, esperado):
    assert elegir_fuente(uri, demo, explicita) == esperado


# ---------------------------------------------------------------- almacen

def test_con_la_api_renueva_en_segundo_plano_sin_hacer_esperar():
    d, _ = _datos()
    lento = threading.Event()
    estado = {"veces": 0}

    def cargador(cfg):
        estado["veces"] += 1
        if estado["veces"] > 1:
            lento.wait(2)  # la renovacion tarda
        return d
    alm = Almacen(_cfg(cache_segundos=0), cargador=cargador)
    primero = alm.obtener()
    inicio = time.monotonic()
    segundo = alm.obtener()                    # vencido: devuelve lo que habia, al instante
    assert time.monotonic() - inicio < 0.5
    assert segundo is primero
    lento.set()


# ---------------------------------------------------------------- servicio completo

@pytest.fixture
def cliente_api(monkeypatch):
    monkeypatch.setenv("FUENTE", "api")
    monkeypatch.setenv("PRECARGAR", "0")
    monkeypatch.delenv("MODO_DEMO", raising=False)
    from app import main as m
    m = importlib.reload(m)
    pedir = sitio_falso()
    m.almacen = Almacen(m.cfg, cargador=lambda cfg: cargar_desde_api(cfg, pedir), en_segundo_plano=False)
    return TestClient(m.app)


def test_endpoints_con_la_fuente_api(cliente_api):
    assert cliente_api.get("/api/indicadores/salud").json() == {"estado": "ok", "fuente": "api"}
    r = cliente_api.get("/api/indicadores/resumen").json()
    assert r["fuente"] == "api" and r["vacantes_abiertas"] == 240
    assert cliente_api.get("/api/indicadores/pronostico/postulaciones").json()["disponible"] is False
    vac = cliente_api.get("/api/indicadores/pronostico/vacantes").json()
    assert vac["disponible"] and "abiertas" in vac["nota"]
    assert cliente_api.get("/api/indicadores/habilidades-usuarios").json()["disponible"] is False
    assert cliente_api.get("/api/indicadores/postulaciones-estado").json()["disponible"] is False
    assert cliente_api.get("/api/indicadores/tendencia-habilidades").status_code == 200


def test_el_servicio_sirve_la_pagina_con_cabeceras_de_seguridad(cliente_api):
    r = cliente_api.get("/")
    assert r.status_code == 200 and "Tendencias y pronóstico" in r.text
    assert "connect-src 'self'" in r.headers["content-security-policy"]
    for recurso in ("assets/js/tendencias.js", "assets/js/base.js", "assets/js/tema.js",
                    "assets/css/app.css", "assets/css/tendencias.css", "assets/img/logo.png"):
        assert cliente_api.get("/" + recurso).status_code == 200, recurso
    # La pagina no trae scripts dentro del HTML (la politica solo permite archivos propios)
    assert "<script>" not in r.text
    assert cliente_api.get("/api/indicadores").json()["fuente"] == "api"
