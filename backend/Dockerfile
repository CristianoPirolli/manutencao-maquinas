# Imagem da API (FastAPI + Uvicorn).
# Construída a partir da raiz do repositório:
#   docker build -f backend/Dockerfile -t manutencao-api .

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # O banco SQLite fica em um volume, fora do código, para sobreviver
    # à recriação do container.
    DATABASE_URL=sqlite:////dados/manutencao.db

WORKDIR /app

# Dependências primeiro: a camada só é refeita quando o requirements muda.
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/ backend/

# Usuário sem privilégios, dono apenas da pasta do banco.
RUN useradd --create-home --uid 1000 app \
    && mkdir /dados \
    && chown app:app /dados
USER app

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=2)"

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
