"""Datos de DEMOSTRACION (inventados) para probar la pagina sin base de datos.

Imitan la forma de los que crea DataSeeder.java (mismas habilidades, ciudades y
estados), pero con una tendencia creciente y habilidades que suben y bajan, para
que el pronostico tenga algo que mostrar. La API avisa siempre que la fuente es
"demo": nunca se deben presentar estas cifras como reales.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from .datos import Datos, ahora, armar_datos

HABILIDADES = [
    "Java", "Spring Boot", "JavaScript", "React", "Angular", "Vue.js", "Node.js", "Python",
    "Django", "Flask", "PHP", "Laravel", "C#", ".NET", "Ruby", "Rails", "Go", "Kotlin",
    "Swift", "Flutter", "React Native", "Docker", "Kubernetes", "AWS", "Azure", "GCP",
    "MySQL", "PostgreSQL", "MongoDB", "Redis", "Git", "CI/CD", "Agile", "Scrum",
    "REST API", "GraphQL", "Microservices", "TDD", "Design Patterns", "SQL",
]
CIUDADES = ["Cartagena", "Bogotá", "Medellín", "Cali", "Barranquilla", "Bucaramanga"]
EMPRESAS = [
    "TechSolutions", "InnovaCode", "DataDrive", "CloudFirst", "DevMasters", "PixelPerfect",
    "CodeCraft", "NextGen Systems", "Digital Dreams", "SmartApps", "WebWizards", "FutureCode",
    "ByteBuilders", "AppGenius", "CyberSoft", "TechVision",
]
SECTORES = ["Tecnología", "Servicios Financieros", "E-commerce", "Educación", "Salud", "Logística", "Turismo"]


class _Coleccion:
    """Lo minimo de una coleccion de pymongo para que armar_datos() lea datos falsos."""

    def __init__(self, docs):
        self.docs = docs

    def find(self, filtro=None, proyeccion=None):
        rol = (filtro or {}).get("roles")
        return [d for d in self.docs if rol is None or rol in d.get("roles", [])]


class _Base:
    def __init__(self, jobs, applications, companies, users):
        self.jobs, self.applications = _Coleccion(jobs), _Coleccion(applications)
        self.companies, self.users = _Coleccion(companies), _Coleccion(users)


def generar_demo(hoy: datetime | None = None, semillas: int = 42) -> Datos:
    rng = np.random.default_rng(semillas)
    hoy = hoy or ahora()
    semanas = 26

    # Popularidad de cada habilidad: unas suben, otras bajan, el resto se mantiene
    peso = np.ones(len(HABILIDADES))
    peso[[HABILIDADES.index(s) for s in ("Python", "React", "Docker", "AWS", "Kubernetes")]] = 1.8
    peso[[HABILIDADES.index(s) for s in ("Java", "JavaScript", "SQL", "Git")]] = 1.6
    sube = [HABILIDADES.index(s) for s in ("Python", "Docker", "AWS", "Kubernetes")]
    baja = [HABILIDADES.index(s) for s in ("Angular", "PHP", "Ruby", "Rails")]

    companies = [{"_id": f"e{i:03d}", "name": n, "industry": SECTORES[i % len(SECTORES)],
                  "location": CIUDADES[i % len(CIUDADES)], "active": True}
                 for i, n in enumerate(EMPRESAS)]
    # Unas empresas publican mucho mas que otras
    peso_empresa = rng.dirichlet(np.linspace(3.0, 0.6, len(EMPRESAS)))

    jobs, applications = [], []
    n_job = 0
    for s in range(semanas):
        inicio = hoy - timedelta(weeks=semanas - 1 - s)
        inicio = (inicio - timedelta(days=inicio.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        avance = s / (semanas - 1)
        # Tendencia creciente + un ciclo suave + ruido
        esperadas = 7 + 9 * avance + 2.0 * np.sin(s / 3.2) + rng.normal(0, 1.2)
        for _ in range(max(0, int(round(esperadas)))):
            p = peso.copy()
            p[sube] *= 1 + 2.2 * avance
            p[baja] *= 1 - 0.8 * avance
            p = p / p.sum()
            habs = rng.choice(len(HABILIDADES), size=int(rng.integers(3, 7)), replace=False, p=p)
            empresa = companies[int(rng.choice(len(companies), p=peso_empresa))]
            fecha = inicio + timedelta(days=int(rng.integers(0, 7)), hours=int(rng.integers(7, 19)))
            if fecha > hoy:
                continue  # aun no ocurre: no se inventan vacantes del futuro
            n_job += 1
            nivel = str(rng.choice(["sin-experiencia", "junior", "semi-senior", "senior"], p=[.2, .35, .3, .15]))
            # El salario sube con la experiencia, mas un poco de variacion
            salario = float(1_300_000 + 700_000 * ["sin-experiencia", "junior", "semi-senior", "senior"].index(nivel)
                            + 250_000 * rng.integers(0, 3))
            jobs.append({
                "_id": f"j{n_job:05d}", "companyId": empresa["_id"],
                "title": "Desarrollador", "type": str(rng.choice(["empleo", "práctica", "freelance"], p=[.6, .25, .15])),
                "experienceLevel": nivel,
                "salaryMin": salario, "salaryMax": salario + 1_000_000,
                "location": str(rng.choice(CIUDADES, p=[.4, .2, .15, .1, .1, .05])),
                "modality": str(rng.choice(["presencial", "remoto", "híbrido"])),
                "skills": [HABILIDADES[i] for i in habs],
                "status": "ABIERTA" if rng.random() > 0.1 else "CERRADA", "active": True,
                "postedDate": fecha,
            })
            # Cada vacante recibe postulaciones durante las dos semanas siguientes
            for _ in range(int(rng.poisson(3.2))):
                f = fecha + timedelta(days=float(rng.exponential(3.5)), hours=float(rng.integers(0, 24)))
                if f > hoy:
                    continue
                aplicada = {"_id": f"a{len(applications):06d}", "jobId": f"j{n_job:05d}",
                            "status": str(rng.choice(["PENDIENTE", "REVISADA", "ACEPTADA", "RECHAZADA"], p=[.4, .25, .1, .25])),
                            "appliedDate": f}
                if aplicada["status"] != "PENDIENTE":
                    aplicada["reviewedDate"] = f + timedelta(days=float(rng.gamma(2.0, 1.5)))
                applications.append(aplicada)

    # Personas: lo que saben no coincide con lo que piden (para que la brecha tenga sentido)
    p_user = np.ones(len(HABILIDADES))
    p_user[[HABILIDADES.index(s) for s in ("JavaScript", "Java", "SQL", "Git", "PHP", "Angular")]] = 3.0
    p_user[[HABILIDADES.index(s) for s in ("Docker", "AWS", "Kubernetes", "Python")]] = 0.5
    p_user = p_user / p_user.sum()
    users = [{"roles": ["USER"],
              "skills": [{"name": HABILIDADES[i]} for i in
                         rng.choice(len(HABILIDADES), size=int(rng.integers(2, 6)), replace=False, p=p_user)]}
             for _ in range(150)]

    return armar_datos(_Base(jobs, applications, companies, users), "demo")
