# Estudo de Caso – Sistema Distribuído (versão 9 adaptada)

**Estratégia escolhida:** alternativa 2 – mesma linguagem (Python) e mesmas bibliotecas
(FastAPI + SQLModel/SQLite no backend, Streamlit no frontend), com **outro modelo conceitual/MER**:
o CRUD de `vendas` foi trocado por um CRUD de **manutenções de máquinas**.

Toda a camada de segurança da versão 9 foi mantida: OAuth2 Password + JWT, perfis e scopes,
access/refresh token com rotação, sessão com `sid`, timeout por inatividade, logout com revogação
e auditoria.

## Novo MER – tabela `manutencao`

| Campo | Tipo | Regra |
|---|---|---|
| id | INTEGER | Chave primária |
| maquina | VARCHAR(100) | Obrigatório, não pode ser só espaços |
| tipo | VARCHAR | `preventiva`, `corretiva` ou `preditiva` |
| data_manutencao | DATE | Não pode ser data futura |
| custo | NUMERIC(10,2) | Maior que zero |
| horas_paradas | NUMERIC(6,1) | Zero ou mais |

(Antes: `venda` com `id`, `item`, `preco_unitario`, `quantidade`.)

As tabelas `usuario`, `refreshtoken`, `logauditoria` e `controleinicializacao` continuam iguais
(só o campo de controle da carga demo foi renomeado para `manutencoes_demo_inseridas`).

## O que mudou em relação ao roteiro

| Vendas (original) | Manutenção (adaptado) |
|---|---|
| `GET /vendas` | `GET /manutencoes` |
| `GET /vendas/qtd-vendas` | `GET /manutencoes/qtd` |
| `GET /vendas/faturamento` (preço × qtd) | `GET /manutencoes/resumo` (custo total + horas paradas) |
| `GET /vendas/busca?nome=&min_qtd=` | `GET /manutencoes/busca?maquina=&tipo=&min_horas=` |
| `GET/PUT/DELETE /vendas/{id}`, `POST /vendas` | `GET/PUT/DELETE /manutencoes/{id}`, `POST /manutencoes` |
| scopes `vendas:read/create/update/delete` | scopes `manutencoes:read/create/update/delete` |
| banco `vendas.db` | banco `manutencao.db` |

No frontend: métricas de custo total, horas paradas e total de manutenções; filtro por máquina,
tipo e horas mínimas; formulários com `selectbox` para o tipo e `date_input` para a data.
O usuário comum continua sem permissão de excluir e sem acesso à auditoria.

## Como executar (PyCharm)

```
pip install -r requirements.txt
uvicorn backend_fastapi:app --reload
streamlit run frontend_streamlit.py      (em outro terminal)
```

Login de administrador: `admin` / `admin123`.
