"""Configurações do frontend.

``API_URL`` pode ser sobrescrita por variável de ambiente para apontar o
frontend para um backend em outra máquina (sistema distribuído).
"""

import os

#: Endereço base da API FastAPI.
API_URL: str = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")

#: Tempo máximo (s) de espera por uma resposta da API.
TIMEOUT: int = 5

#: Tempo máximo (s) do health check exibido na barra lateral.
TIMEOUT_HEALTH_CHECK: int = 2

#: Valor inicial do timeout de inatividade; o prazo efetivo vem do backend.
SESSION_IDLE_SECONDS: int = 30 * 60

#: Tipos válidos de manutenção (devem coincidir com o backend).
TIPOS_MANUTENCAO: tuple[str, ...] = ("preventiva", "corretiva", "preditiva")

#: Cor de cada tipo, seguindo o código de cores de segurança industrial:
#: azul = ação planejada, vermelho = falha, verde = condição monitorada.
CORES_TIPO: dict[str, str] = {
    "preventiva": "#2F6FB2",
    "corretiva": "#C8332B",
    "preditiva": "#2E8B57",
}

#: Campos obrigatórios de uma manutenção completa retornada pela API.
CAMPOS_MANUTENCAO: frozenset[str] = frozenset(
    {"id", "maquina", "tipo", "data_manutencao", "custo", "horas_paradas"}
)

#: Prefixo da chave do ``st.dataframe`` de registros.
CHAVE_TABELA: str = "tabela_manutencoes"
