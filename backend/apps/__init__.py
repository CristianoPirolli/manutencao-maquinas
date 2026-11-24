"""Apps de domínio do backend.

Cada app segue a mesma convenção de arquivos:

- ``models.py``: tabelas do banco (SQLModel com ``table=True``).
- ``schemas.py``: contratos de entrada e saída da API.
- ``service.py``: regras de negócio, independentes do protocolo HTTP.
- ``router.py``: endpoints FastAPI que expõem o app.
"""
