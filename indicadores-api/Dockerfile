# Servicio de indicadores de SkillMatch (aparte del backend Java). Sirve la API y la pagina.
# Construir:  docker build -t skillmatch-indicadores .
# Probar:     docker run -p 8000:8000 skillmatch-indicadores      ->  http://localhost:8000
#             (sin variables lee la API publica de SkillMatch; con -e MODO_DEMO=1, datos inventados)
FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PORT=8000
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY web ./web
RUN adduser --system --no-create-home app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/api/indicadores/salud')" || exit 1
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers"]
