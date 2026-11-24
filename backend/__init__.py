"""Backend da API de Manutenção de Máquinas (FastAPI + SQLModel).

O pacote está organizado em duas camadas:

- ``backend.core``: infraestrutura compartilhada (configuração, banco de dados,
  segurança e inicialização).
- ``backend.apps``: módulos de domínio independentes, cada um com seus próprios
  modelos, schemas, regras de negócio e rotas.

O ponto de entrada ASGI é ``backend.main:app``.
"""
