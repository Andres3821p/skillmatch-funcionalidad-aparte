"""Modelos predictivos del modulo de indicadores.

Hay dos, pensados para pocos datos (decenas de semanas, no miles):

1. pronostico_semanal(): cuantas vacantes / postulaciones habra en las proximas semanas.
   Compara tres modelos sencillos con una prueba hacia atras ("backtesting") y se queda
   con el que menos se equivoco; si ninguno supera claramente al promedio simple, usa
   el promedio simple. Asi el sistema no presume un modelo sofisticado que no aporta.

2. tendencia_habilidades(): que habilidades suben o bajan en las vacantes. Ajusta una
   recta al porcentaje semanal de cada habilidad. Con pocas vacantes por semana el azar
   mueve mucho esos porcentajes, asi que cada habilidad lleva una etiqueta de evidencia:
   "firme" si el cambio sigue siendo creible despues de controlar los falsos positivos
   (Benjamini-Hochberg; con 40 habilidades, algunas "subirian" por pura casualidad) y
   "debil" si podria ser azar.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import numpy as np
from scipy import stats

from .datos import Datos
from .indicadores import lunes

Z80 = 1.2816          # intervalo de ~80 %
MIN_SEMANAS = 8       # semanas completas minimas para pronosticar
VENTANA_LINEAL = 12   # la tendencia lineal mira solo las ultimas 12 semanas


# ---------------------------------------------------------------- los tres modelos

def modelo_promedio(y: np.ndarray, h: int) -> np.ndarray:
    """Base de comparacion: lo mismo que el promedio de las ultimas 4 semanas."""
    return np.full(h, y[-4:].mean())


def modelo_lineal(y: np.ndarray, h: int) -> np.ndarray:
    """Recta de minimos cuadrados sobre las ultimas semanas, prolongada hacia adelante."""
    y = y[-VENTANA_LINEAL:]
    pendiente, intercepto = np.polyfit(np.arange(len(y)), y, 1)
    return np.clip(intercepto + pendiente * np.arange(len(y), len(y) + h), 0, None)


def _holt(y: np.ndarray, a: float, b: float, phi: float):
    nivel = y[0]
    tend = (y[min(2, len(y) - 1)] - y[0]) / max(1, min(2, len(y) - 1))
    sse = 0.0
    for v in y[1:]:
        pred = nivel + phi * tend
        sse += (v - pred) ** 2
        nuevo = a * v + (1 - a) * pred
        tend = b * (nuevo - nivel) + (1 - b) * phi * tend
        nivel = nuevo
    return nivel, tend, sse


def modelo_holt(y: np.ndarray, h: int) -> np.ndarray:
    """Suavizado exponencial con tendencia amortiguada (Holt): la tendencia se va apagando
    en vez de crecer para siempre. Los parametros se escogen minimizando el error."""
    rejilla = [(a, b, p) for a in (.2, .4, .6, .8) for b in (.1, .3) for p in (.8, .9, .98)]
    a, b, phi = min(rejilla, key=lambda par: _holt(y, *par)[2])
    nivel, tend, _ = _holt(y, a, b, phi)
    pasos = np.cumsum([phi ** k for k in range(1, h + 1)])
    return np.clip(nivel + tend * pasos, 0, None)


MODELOS = {
    "promedio": ("Promedio de las últimas 4 semanas", modelo_promedio),
    "lineal": ("Tendencia lineal", modelo_lineal),
    "holt": ("Suavizado exponencial con tendencia", modelo_holt),
}


def _backtest(y: np.ndarray) -> dict[str, list[float]]:
    """Para cada semana de la segunda mitad: predecirla usando solo lo anterior y medir el error."""
    inicio = max(6, len(y) // 2)
    return {k: [float(y[t] - f(y[:t], 1)[0]) for t in range(inicio, len(y))]
            for k, (_, f) in MODELOS.items()}


# ---------------------------------------------------------------- pronostico

def pronostico_semanal(serie: list[dict], horizonte: int = 4, unidad: str = "vacantes") -> dict:
    """`serie`: [{'semana': 'YYYY-MM-DD', 'valor': n, 'parcial': bool}, ...] (ver indicadores.serie_semanal)."""
    completas = [p for p in serie if not p["parcial"]]
    # Las semanas en cero antes del primer dato son "la plataforma aun no existia": no entrenan
    while completas and completas[0]["valor"] == 0:
        completas.pop(0)
    if len(completas) < MIN_SEMANAS:
        return {"disponible": False,
                "motivo": f"Hacen falta al menos {MIN_SEMANAS} semanas completas con datos; hay {len(completas)}."}

    y = np.array([p["valor"] for p in completas], dtype=float)
    errores = _backtest(y)
    mae = {k: float(np.mean(np.abs(e))) for k, e in errores.items()}
    # Se elige el de menor error; si no le gana al promedio por mas de 5 %, se queda el promedio
    mejor = min(mae, key=lambda k: (mae[k], list(MODELOS).index(k)))
    if mae[mejor] > mae["promedio"] * 0.95:
        mejor = "promedio"
    base = mae["promedio"]
    mejora = round((base - mae[mejor]) / base * 100, 1) if base > 0 else 0.0

    sigma = max(float(np.sqrt(np.mean(np.square(errores[mejor])))), 0.5)
    pred = MODELOS[mejor][1](y, horizonte)
    ultima = date.fromisoformat(completas[-1]["semana"])
    en_curso = bool(serie and serie[-1]["parcial"])
    puntos = []
    for i, v in enumerate(pred, start=1):
        margen = Z80 * sigma * np.sqrt(i)  # la incertidumbre crece con la distancia
        puntos.append({"semana": (ultima + timedelta(weeks=i)).isoformat(),
                       "valor": round(float(v), 1),
                       "minimo": round(max(0.0, float(v) - float(margen)), 1),
                       "maximo": round(float(v) + float(margen), 1),
                       "en_curso": en_curso and i == 1})

    reciente = float(y[-4:].mean())
    esperado = float(np.mean(pred))
    cambio = (esperado - reciente) / reciente if reciente > 0 else 0.0
    tendencia = "sube" if cambio > 0.10 else "baja" if cambio < -0.10 else "estable"

    if mejora >= 10:
        calidad = f"En las pruebas con semanas pasadas, este modelo se equivocó {str(round(mejora, 1)).replace('.', ',')} % menos que el promedio simple."
    elif mejor != "promedio" and mejora > 0:
        calidad = "En las pruebas con semanas pasadas apenas mejora al promedio simple; tómalo como una referencia."
    else:
        calidad = "Ningún modelo superó claramente al promedio simple con los datos actuales; es solo una referencia."
    lectura = (f"Se esperan unas {round(esperado)} {unidad} por semana en las próximas {horizonte} semanas "
               f"(rango probable por semana: {round(min(p['minimo'] for p in puntos))} a "
               f"{round(max(p['maximo'] for p in puntos))}). En las últimas 4 semanas hubo {round(reciente)} por semana. {calidad}")

    return {
        "disponible": True,
        "unidad": unidad,
        "modelo": mejor,
        "modelo_nombre": MODELOS[mejor][0],
        "tendencia": tendencia,
        "lectura": lectura,
        "evaluacion": {
            "semanas_usadas": len(y),
            "mae": round(mae[mejor], 2),
            "mae_base": round(base, 2),
            "mejora_pct": mejora,
            "modelos": [{"id": k, "nombre": MODELOS[k][0], "mae": round(v, 2)} for k, v in mae.items()],
        },
        # La grafica empieza en la primera semana con datos (antes la plataforma aun no tenia nada)
        "historico": serie[next((i for i, p in enumerate(serie) if p["valor"] > 0), 0):],
        "pronostico": puntos,
    }


# ---------------------------------------------------------------- habilidades que suben o bajan

def _benjamini_hochberg(p: list[float], q: float = 0.10) -> list[bool]:
    """Marca cuales p-valores siguen siendo significativos controlando la tasa de falsos descubrimientos."""
    m = len(p)
    orden = sorted(range(m), key=lambda i: p[i])
    corte = -1
    for rango, i in enumerate(orden, start=1):
        if p[i] <= q * rango / m:
            corte = rango
    ok = [False] * m
    for rango, i in enumerate(orden, start=1):
        ok[i] = rango <= corte
    return ok


def tendencia_habilidades(d: Datos, hoy: datetime | None = None, semanas: int = 12,
                          top: int = 12, min_menciones: int = 8, min_cambio_pp: float = 0.3) -> dict:
    hoy = hoy or d.cargado
    actual = lunes(hoy)
    inicio = actual - timedelta(weeks=semanas)
    v = d.vacantes[d.vacantes["activa"]]
    semana_de = {}
    totales = np.zeros(semanas)
    for pub, habs in zip(v["publicada"], v["habilidades"]):
        if pub != pub:  # NaT
            continue
        s = (lunes(pub) - inicio).days // 7
        if 0 <= s < semanas:  # la semana en curso queda fuera: esta incompleta
            totales[s] += 1
            for h in habs:
                semana_de.setdefault(h, np.zeros(semanas))[s] += 1

    validas = np.where(totales > 0)[0]
    if len(validas) < 5:
        return {"disponible": False,
                "motivo": "Hacen falta al menos 5 semanas con vacantes publicadas para ver tendencias."}

    filas = []
    for nombre, c in semana_de.items():
        if c.sum() < min_menciones:
            continue
        x = validas.astype(float)
        porcentaje = 100 * c[validas] / totales[validas]
        r = stats.linregress(x, porcentaje)
        ultimas = validas[-4:]
        filas.append({
            "nombre": nombre,
            "menciones": int(c.sum()),
            "porcentaje_actual": round(float(100 * c[ultimas].sum() / totales[ultimas].sum()), 1),
            "cambio_pp_semana": round(float(r.slope), 2),
            "proyeccion_4_semanas": round(float(np.clip(r.intercept + r.slope * (validas[-1] + 4), 0, 100)), 1),
            # % de las vacantes de cada semana que la piden: es lo que dibuja la mini-línea
            "serie": [round(float(v), 1) for v in porcentaje],
            "_p": float(r.pvalue) if r.pvalue == r.pvalue else 1.0,
        })
    if not filas:
        return {"disponible": False, "motivo": "Ninguna habilidad aparece lo suficiente para medir su tendencia."}

    significativas = _benjamini_hochberg([f["_p"] for f in filas])
    for f, ok in zip(filas, significativas):
        f["tendencia"] = ("sube" if f["cambio_pp_semana"] > 0 else "baja") \
            if abs(f["cambio_pp_semana"]) >= min_cambio_pp else "estable"
        f["evidencia"] = "firme" if ok and f["tendencia"] != "estable" else "débil"
        del f["_p"]
    filas.sort(key=lambda f: (-f["cambio_pp_semana"], f["nombre"].lower()))
    return {
        "disponible": True,
        "semanas_analizadas": int(len(validas)),
        "vacantes_analizadas": int(totales.sum()),
        "habilidades_evaluadas": len(filas),
        "suben": [f for f in filas if f["tendencia"] == "sube"][:top],
        "bajan": [f for f in reversed(filas) if f["tendencia"] == "baja"][:top],
    }
