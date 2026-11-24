# Referência da API

Base: `http://127.0.0.1:8000` · Swagger: `/docs` · ReDoc: `/redoc`

Rotas protegidas exigem o cabeçalho `Authorization: Bearer <access_token>`.
Erros seguem o padrão do FastAPI: `{"detail": "..."}`.

## Status

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/` | — | Health check: `{"mensagem": "API está no ar!", "versao": "9"}` |

## Autenticação

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/token` | — | Login (form `username`, `password`, `scope` opcional) |
| POST | `/refresh` | — | Corpo `{"refresh_token": "..."}`; devolve novo par de tokens |
| POST | `/logout` | — | Corpo `{"refresh_token": "..."}`; encerra a sessão |

Resposta de `/token` e `/refresh`:

```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "Yp3k...",
  "token_type": "bearer",
  "expires_in": 900,
  "refresh_expires_in": 604800,
  "session_idle_seconds": 1800,
  "usuario": {
    "id": 1,
    "username": "admin",
    "role": "admin",
    "scopes": ["auditoria:read", "manutencoes:create", "manutencoes:delete",
               "manutencoes:read", "manutencoes:update"],
    "sessao_id": "0f1c..."
  }
}
```

## Usuários

| Método | Rota | Scope | Descrição |
|---|---|---|---|
| POST | `/usuarios` | — | Cria conta comum: `{"username": "...", "senha": "..."}` (201, 409 se existir) |
| GET | `/me` | qualquer | Perfil e scopes efetivos da sessão |

## Máquinas

| Método | Rota | Scope | Descrição |
|---|---|---|---|
| GET | `/maquinas` | `maquinas:read` | Lista em ordem alfabética, com `total_manutencoes` |
| GET | `/maquinas/indicadores` | `maquinas:read` + `manutencoes:read` | MTTR, MTBF e disponibilidade de cada máquina |
| GET | `/maquinas/{id}` | `maquinas:read` | Uma máquina (404 se não existir) |
| POST | `/maquinas` | `maquinas:create` | Cadastra (201; 409 se o nome já existir) |
| PUT | `/maquinas/{id}` | `maquinas:update` | Altera nome e setor (409 se o nome já existir) |
| DELETE | `/maquinas/{id}` | `maquinas:delete` | Exclui (409 se houver manutenções registradas) |

Corpo de `POST` / `PUT`: `{"nome": "Prensa hidráulica PH-4", "setor": "Prensagem"}`
(`setor` é opcional). Resposta de `GET /maquinas`:

```json
[
  {"id": 1, "nome": "Bobinadeira 01", "setor": "Acabamento", "total_manutencoes": 2}
]
```

### Indicadores de confiabilidade

`GET /maquinas/indicadores` considera **só as manutenções corretivas** como falha:

| Campo | Fórmula | Nulo quando |
|---|---|---|
| `mttr_horas` | horas paradas nas falhas ÷ número de falhas | nenhuma falha |
| `mtbf_horas` | média, entre falhas seguidas, de (dias entre elas × 24 − horas paradas na primeira) | menos de 2 falhas |
| `disponibilidade` | MTBF ÷ (MTBF + MTTR), de 0 a 1 | menos de 2 falhas |

```json
[
  {"maquina_id": 1, "maquina": "Bobinadeira 01", "setor": "Acabamento", "falhas": 2,
   "mttr_horas": "7.3", "mtbf_horas": "2154.0", "disponibilidade": "0.997"}
]
```

## Manutenções

| Método | Rota | Scope | Descrição |
|---|---|---|---|
| GET | `/manutencoes` | `manutencoes:read` | Todas, no formato `{id: manutencao}` |
| GET | `/manutencoes/qtd` | `manutencoes:read` | `{"quantidade_total": 8}` |
| GET | `/manutencoes/resumo` | `manutencoes:read` | `{"custo_total": "31100.50", "horas_paradas_total": "54.5", "moeda": "R$"}` |
| GET | `/manutencoes/busca` | `manutencoes:read` | Filtros `maquina` (trecho do nome), `maquina_id`, `tipo`, `min_horas`; mais recentes primeiro |
| GET | `/manutencoes/{id}` | `manutencoes:read` | Uma manutenção (404 se não existir) |
| POST | `/manutencoes` | `manutencoes:create` | Cria (201; 422 se a máquina não existir) |
| PUT | `/manutencoes/{id}` | `manutencoes:update` | Substitui todos os campos |
| DELETE | `/manutencoes/{id}` | `manutencoes:delete` | Exclui |

Corpo de `POST` / `PUT` (a máquina é informada pelo `id` do cadastro):

```json
{
  "maquina_id": 1,
  "tipo": "corretiva",
  "data_manutencao": "2026-11-10",
  "custo": "2780.50",
  "horas_paradas": "8.5"
}
```

As respostas trazem `maquina_id` e também `maquina` (o nome), para o cliente
não precisar de uma segunda consulta. Valores decimais são trafegados como
texto para preservar a precisão.

## Auditoria

| Método | Rota | Scope | Descrição |
|---|---|---|---|
| GET | `/auditoria?limite=100` | `auditoria:read` | Últimos registros (1 a 500) |

## Códigos de status

| Código | Quando |
|---|---|
| 200 / 201 | Sucesso |
| 400 | Scope solicitado não permitido ao perfil |
| 401 | Token ausente, inválido ou expirado; sessão encerrada; credenciais inválidas |
| 403 | Token válido, mas sem o scope exigido pela rota |
| 404 | Máquina ou manutenção inexistente |
| 409 | Nome de usuário ou de máquina já cadastrado; máquina com histórico não pode ser excluída |
| 422 | Dados de entrada inválidos (validação Pydantic) ou máquina informada não cadastrada |

## Exemplo com `curl`

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/token \
  -d "username=admin&password=admin123" | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s http://127.0.0.1:8000/manutencoes/resumo -H "Authorization: Bearer $TOKEN"
```
