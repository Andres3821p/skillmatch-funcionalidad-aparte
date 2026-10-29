import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def main(monkeypatch):
    monkeypatch.setenv("MODO_DEMO", "1")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://skillmatch-yz37.onrender.com")
    from app import main as m
    return importlib.reload(m)


@pytest.fixture
def cliente(main):
    return TestClient(main.app)


def test_salud_no_toca_la_base(cliente):
    r = cliente.get("/api/indicadores/salud")
    assert r.status_code == 200 and r.json() == {"estado": "ok", "fuente": "demo"}


@pytest.mark.parametrize("ruta", [
    "resumen", "habilidades-demandadas", "empresas-activas", "habilidades-usuarios",
    "brecha-habilidades", "salarios", "postulaciones-estado", "series",
    "pronostico/vacantes", "pronostico/postulaciones", "tendencia-habilidades"])
def test_todos_los_endpoints_responden_y_se_pueden_guardar_en_cache(cliente, ruta):
    r = cliente.get(f"/api/indicadores/{ruta}")
    assert r.status_code == 200
    assert "max-age" in r.headers["cache-control"]


def test_el_resumen_avisa_que_es_demostracion(cliente):
    assert cliente.get("/api/indicadores/resumen").json()["fuente"] == "demo"


def test_pronostico_valida_la_serie_y_el_horizonte(cliente):
    assert cliente.get("/api/indicadores/pronostico/otra").status_code == 404
    assert cliente.get("/api/indicadores/pronostico/vacantes?semanas=99").status_code == 422
    r = cliente.get("/api/indicadores/pronostico/vacantes?semanas=3").json()
    assert len(r["pronostico"]) == 3


def test_top_fuera_de_rango_es_422(cliente):
    assert cliente.get("/api/indicadores/habilidades-demandadas?top=0").status_code == 422
    assert cliente.get("/api/indicadores/habilidades-demandadas?top=500").status_code == 422


def test_cors_permite_localhost_y_el_sitio_configurado_pero_no_otros(cliente):
    def origen(o):
        return cliente.get("/api/indicadores/salud", headers={"Origin": o}).headers.get("access-control-allow-origin")
    assert origen("http://localhost:5500") == "http://localhost:5500"
    assert origen("https://skillmatch-yz37.onrender.com") == "https://skillmatch-yz37.onrender.com"
    assert origen("https://sitio-ajeno.example") is None


def test_si_mongo_falla_responde_503_sin_filtrar_la_uri(main, cliente):
    def roto(cfg):
        raise RuntimeError("mongodb+srv://usuario:clave@cluster/skillmatch no responde")
    main.almacen = main.Almacen(main.cfg, cargador=roto)
    r = cliente.get("/api/indicadores/resumen")
    assert r.status_code == 503
    assert "clave" not in r.text and "mongodb" not in r.text


def test_si_mongo_falla_despues_de_cargar_sirve_lo_ultimo(main, cliente):
    from app.demo import generar_demo
    estado = {"falla": False}

    def cargador(cfg):
        if estado["falla"]:
            raise RuntimeError("caido")
        return generar_demo()
    main.almacen = main.Almacen(main.cfg, cargador=cargador)
    main.cfg = main.cfg.__class__(**{**main.cfg.__dict__, "cache_segundos": 0})
    main.almacen.cfg = main.cfg
    assert cliente.get("/api/indicadores/resumen").json()["desactualizado"] is False
    estado["falla"] = True
    r = cliente.get("/api/indicadores/resumen")
    assert r.status_code == 200 and r.json()["desactualizado"] is True
