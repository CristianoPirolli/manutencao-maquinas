# Imagem da interface (Streamlit).
# Construída a partir da raiz do repositório:
#   docker build -f frontend/Dockerfile -t manutencao-web .

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Endereço da API visto de dentro do container; o docker-compose
    # sobrescreve com o nome do serviço (http://api:8000).
    API_URL=http://127.0.0.1:8000

WORKDIR /app

COPY frontend/requirements.txt frontend/requirements.txt
RUN pip install -r frontend/requirements.txt

# O tema (.streamlit/config.toml) é lido do diretório de trabalho.
COPY .streamlit/config.toml .streamlit/config.toml
COPY frontend/ frontend/

RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8501

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=2)"

CMD ["streamlit", "run", "frontend/app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
