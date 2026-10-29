"""Calculo de indicadores. Son funciones puras: reciben `Datos` y devuelven diccionarios
listos para convertirse en JSON, asi se prueban sin base de datos ni servidor."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

import pandas as pd

from .datos import Datos, clave

# Una habilidad suelta de menos de 3 personas no se publica en el ranking de personas
MIN_PERSONAS = 3
# La brecha solo es confiable con una base minima de personas y de vacantes
MIN_BASE_BRECHA = 10

NIVELES = [("sin-experiencia", "Sin experiencia"), ("junior", "Hasta 1 año"),
           ("semi-senior", "De 1 a 3 años"), ("senior", "Más de 3 años")]


def _pct(parte: float, total: float) -> float:
    return round(parte / total * 100, 1) if total else 0.0


def contar_habilidades(listas) -> tuple[list[tuple[str, int]], int]:
    """Cuantas listas mencionan cada habilidad (una vez por lista). Devuelve (ranking, total_listas).

    'Node.js' y 'node.js' se juntan; se muestra la escritura mas frecuente.
    """
    veces: Counter = Counter()
    escrituras: dict[str, Counter] = defaultdict(Counter)
    total = 0
    for lista in listas:
        total += 1
        for nombre in lista:
            k = clave(nombre)
            veces[k] += 1
            escrituras[k][nombre] += 1
    ranking = [(escrituras[k].most_common(1)[0][0], n) for k, n in veces.items()]
    ranking.sort(key=lambda x: (-x[1], x[0].lower()))
    return ranking, total


def _barras(ranking, total, top):
    return [{"nombre": n, "valor": v, "porcentaje": _pct(v, total)} for n, v in ranking[:top]]


# ---------------------------------------------------------------- tres tarjetas

def habilidades_demandadas(d: Datos, top: int = 10) -> dict:
    ranking, total = contar_habilidades(d.abiertas["habilidades"])
    return {"base": total, "unidad": "vacantes abiertas", "items": _barras(ranking, total, top)}


def habilidades_usuarios(d: Datos, top: int = 10) -> dict:
    ranking, total = contar_habilidades(d.habilidades_usuarios)
    visibles = [(n, v) for n, v in ranking if v >= MIN_PERSONAS]
    return {"base": total, "unidad": "personas registradas", "items": _barras(visibles, total, top)}


def empresas_activas(d: Datos, top: int = 10, hoy: datetime | None = None, dias: int = 90) -> dict:
    """Actividad = vacantes publicadas en los ultimos `dias`; desempata con las postulaciones recibidas."""
    hoy = hoy or d.cargado
    desde = pd.Timestamp(hoy - timedelta(days=dias))
    v = d.vacantes
    recientes = v[(v["publicada"] >= desde) & v["activa"]]
    por_empresa = recientes.groupby("empresa_id").size()
    abiertas = d.abiertas.groupby("empresa_id").size()
    recibidas = (d.postulaciones.merge(v[["id", "empresa_id"]], left_on="vacante_id", right_on="id", how="inner")
                 .groupby("empresa_id").size())
    nombres = d.empresas.set_index("id")["nombre"].to_dict()
    sectores = d.empresas.set_index("id")["sector"].to_dict()
    filas = []
    for emp_id, n in por_empresa.items():
        if emp_id not in nombres:
            continue  # vacantes de una empresa que ya no existe
        filas.append({"nombre": nombres[emp_id], "sector": sectores.get(emp_id, ""),
                      "valor": int(n), "abiertas": int(abiertas.get(emp_id, 0)),
                      "postulaciones": int(recibidas.get(emp_id, 0))})
    filas.sort(key=lambda f: (-f["valor"], -f["postulaciones"], f["nombre"].lower()))
    total = int(por_empresa.sum())
    for f in filas:
        f["porcentaje"] = _pct(f["valor"], total)
    return {"base": total, "unidad": f"vacantes publicadas en {dias} días", "items": filas[:top]}


# ---------------------------------------------------------------- brecha oferta / demanda

def brecha_habilidades(d: Datos, top: int = 5) -> dict:
    """Que piden las empresas y cuantas personas lo tienen. Diferencia en puntos porcentuales:
    (% de vacantes que la piden) - (% de personas que la tienen). Positivo = hace falta."""
    demanda, n_v = contar_habilidades(d.abiertas["habilidades"])
    oferta, n_p = contar_habilidades(d.habilidades_usuarios)
    if n_v < MIN_BASE_BRECHA or n_p < MIN_BASE_BRECHA:
        return {"disponible": False,
                "motivo": f"Hacen falta al menos {MIN_BASE_BRECHA} vacantes abiertas y {MIN_BASE_BRECHA} personas con habilidades."}
    dem = {clave(n): (n, v) for n, v in demanda}
    ofe = {clave(n): (n, v) for n, v in oferta}
    filas = []
    for k in dem.keys() | ofe.keys():
        nombre = (dem.get(k) or ofe.get(k))[0]
        pd_, po = _pct(dem.get(k, (0, 0))[1], n_v), _pct(ofe.get(k, (0, 0))[1], n_p)
        filas.append({"nombre": nombre, "demanda": pd_, "oferta": po, "brecha": round(pd_ - po, 1)})
    filas.sort(key=lambda f: (-f["brecha"], f["nombre"].lower()))
    faltan = [f for f in filas if f["brecha"] > 0][:top]
    sobran = [f for f in sorted(filas, key=lambda f: (f["brecha"], f["nombre"].lower())) if f["brecha"] < 0][:top]
    return {"disponible": True, "base_vacantes": n_v, "base_personas": n_p, "faltan": faltan, "sobran": sobran}


# ---------------------------------------------------------------- series semanales

def lunes(f) -> date:
    f = f.date() if isinstance(f, (datetime, pd.Timestamp)) else f
    return f - timedelta(days=f.weekday())


def serie_semanal(fechas: pd.Series, hoy: datetime, semanas: int = 26) -> list[dict]:
    """Conteo por semana (lunes a domingo) de las ultimas `semanas`. La semana en curso
    va marcada como parcial: todavia no termino y no debe usarse para entrenar modelos."""
    actual = lunes(hoy)
    inicio = actual - timedelta(weeks=semanas - 1)
    conteo: Counter = Counter()
    for f in fechas.dropna():
        if f <= pd.Timestamp(hoy) and lunes(f) >= inicio:
            conteo[lunes(f)] += 1
    return [{"semana": (inicio + timedelta(weeks=i)).isoformat(),
             "valor": conteo.get(inicio + timedelta(weeks=i), 0),
             "parcial": i == semanas - 1} for i in range(semanas)]


def series(d: Datos, hoy: datetime | None = None, semanas: int = 26) -> dict:
    hoy = hoy or d.cargado
    return {"vacantes": serie_semanal(d.vacantes.loc[d.vacantes["activa"], "publicada"], hoy, semanas),
            "postulaciones": serie_semanal(d.postulaciones["fecha"], hoy, semanas)}


# ---------------------------------------------------------------- otros indicadores

def salarios_por_experiencia(d: Datos) -> dict:
    a = d.abiertas
    a = a[a["salario_min"].notna() & (a["salario_min"] > 0)]
    items = []
    for k, etiqueta in NIVELES:
        s = a.loc[a["experiencia"] == k, "salario_min"]
        if len(s):
            items.append({"nombre": etiqueta, "valor": int(s.median()), "vacantes": int(len(s))})
    return {"unidad": "mediana del salario mínimo publicado, en pesos", "items": items}


def embudo_postulaciones(d: Datos) -> dict:
    cuenta = d.postulaciones["estado"].value_counts().to_dict()
    total = int(sum(cuenta.values()))
    orden = [("pendiente", "Pendientes"), ("revisada", "Revisadas"),
             ("aceptada", "Aceptadas"), ("rechazada", "Rechazadas")]
    return {"base": total, "items": [{"nombre": n, "valor": int(cuenta.get(k, 0)),
                                       "porcentaje": _pct(cuenta.get(k, 0), total)} for k, n in orden]}


def resumen(d: Datos) -> dict:
    abiertas = d.abiertas
    n_ab = int(len(abiertas))
    n_post = int(len(d.postulaciones))
    p = d.postulaciones
    respuesta = (p["revisada"] - p["fecha"]).dropna().dt.total_seconds() / 86400
    respuesta = respuesta[respuesta >= 0]
    return {
        "vacantes_abiertas": n_ab,
        "empresas_activas": int(d.empresas["activa"].sum()),
        "personas": int(len(d.habilidades_usuarios)),
        "postulaciones": n_post,
        "postulaciones_por_vacante": round(n_post / n_ab, 1) if n_ab else None,
        "dias_mediana_respuesta": round(float(respuesta.median()), 1) if len(respuesta) else None,
        "fuente": d.fuente,
        "actualizado": d.cargado.isoformat(timespec="seconds") + "Z",
        "desactualizado": d.desactualizado,
    }
