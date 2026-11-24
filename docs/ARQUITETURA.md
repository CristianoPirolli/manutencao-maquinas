# Arquitetura

Este documento descreve como o projeto está organizado e por quê.

## Visão geral

O sistema tem dois processos independentes que se comunicam apenas por HTTP/JSON —
por isso podem rodar em máquinas diferentes (sistema distribuído):

```mermaid
flowchart LR
    U([Usuário]) -->|navegador| F[Frontend Streamlit<br/>:8501]
    F -->|HTTP + JSON<br/>Bearer JWT| B[Backend FastAPI<br/>:8000]
    B -->|SQLModel / SQLAlchemy| D[(SQLite<br/>manutencao.db)]
```

O frontend **não acessa o banco**: toda regra de negócio e de segurança vive no
backend. As validações feitas no frontend servem apenas para dar retorno
rápido ao usuário e são sempre repetidas pela API.

## Do monólito aos apps

O roteiro entrega cada lado em um único arquivo (`backend_fastapi.py` com ~1.300
linhas e `frontend_streamlit.py` com ~1.000). O projeto foi reorganizado em
**pacotes por responsabilidade**, de forma semelhante aos *apps* do Django:

| Camada | Responsabilidade | Pode importar de |
|---|---|---|
| `core/` | Infraestrutura transversal (config, banco, segurança) | bibliotecas externas |
| `apps/<dominio>/` | Um domínio de negócio completo | `core/` e outros apps |
| `main.py` / `app.py` | Montagem da aplicação | tudo |

### Convenção de arquivos dos apps do backend

| Arquivo | Conteúdo |
|---|---|
| `models.py` | Tabelas (`SQLModel, table=True`) |
| `schemas.py` | Contratos de entrada e saída da API |
| `service.py` | Regras de negócio, sem conhecimento de rotas |
| `router.py` | Endpoints (`APIRouter`) — finos, delegam ao `service` |
| `dependencies.py` | Dependências FastAPI (apenas em `autenticacao`) |

Separar `router` de `service` permite testar e reutilizar regras sem passar pelo
HTTP e mantém cada endpoint com poucas linhas.

### Dependências entre apps do backend

```mermaid
flowchart TD
    main[main.py] --> autenticacao & usuarios & manutencoes & auditoria
    manutencoes --> autenticacao
    usuarios --> autenticacao
    auditoria_r[auditoria.router] --> autenticacao
    autenticacao --> usuarios_m[usuarios.models / service]
    autenticacao --> auditoria_s[auditoria.service]
    manutencoes --> auditoria_s
    usuarios --> auditoria_s
    subgraph core
      config --> security
      config --> database
    end
    autenticacao & usuarios & manutencoes & auditoria --> core
```

Não há ciclos: `auditoria.service` e `usuarios.models` são "folhas" usadas pelos
demais apps.

### Frontend

O Streamlit re-executa `frontend/app.py` inteiro a cada interação. Esse arquivo
apenas define **a ordem das telas**; cada tela é uma função `renderizar_*` em
`frontend/apps/<dominio>/views.py`.

| Módulo | Papel |
|---|---|
| `core/api_client.py` | Única porta de saída para a API; renova o token em caso de 401 |
| `core/estado.py` | Única porta de acesso ao `st.session_state` |
| `core/formatadores.py` | Funções puras (testáveis sem Streamlit) |
| `apps/*/views.py` | Desenho das telas |
| `apps/manutencoes/formulario.py` | Validação e serialização do formulário (pura) |

## Fluxos de segurança

### Login e uso de rota protegida

```mermaid
sequenceDiagram
    participant F as Frontend
    participant A as API
    participant DB as Banco
    F->>A: POST /token (usuário, senha)
    A->>DB: verifica hash Argon2
    A->>DB: grava RefreshToken (hash SHA-256, sessao_id)
    A-->>F: access_token (JWT 15 min, com sid) + refresh_token
    F->>A: GET /manutencoes (Bearer JWT)
    A->>A: valida assinatura/expiração do JWT
    A->>DB: sessão sid ativa? pertence ao usuário? inativa há < 30 min?
    A->>A: scopes do token ∩ scopes do perfil atual ⊇ scopes da rota?
    A->>DB: atualiza ultima_atividade
    A-->>F: 200 + dados
```

### Renovação automática (refresh com rotação)

```mermaid
sequenceDiagram
    participant F as Frontend
    participant A as API
    F->>A: GET /recurso (JWT expirado)
    A-->>F: 401 Access token expirado
    F->>A: POST /refresh (refresh_token atual)
    A->>A: revoga token atual (UPDATE condicional e atômico)
    A-->>F: novo access_token + novo refresh_token (mesmo sid)
    F->>A: repete GET /recurso
    A-->>F: 200
```

Se o mesmo refresh token for usado duas vezes (vazamento ou requisições
concorrentes), a segunda tentativa é tratada como **reuso**: a sessão inteira
é revogada, invalidando também o token emitido na rotação (detecção de reuso,
RFC 6819 / OAuth 2.0 Security BCP). O usuário legítimo precisa entrar de novo.

### Encerramento de sessão

| Evento | Efeito |
|---|---|
| `POST /logout` | Revoga todos os refresh tokens da sessão; o JWT ainda válido passa a ser recusado porque o `sid` não está mais ativo |
| 30 min sem atividade | Próxima chamada revoga a sessão e retorna 401 |
| Refresh token com mais de 7 dias | Sessão revogada |
| Perfil do usuário rebaixado | Scopes efetivos são recalculados a cada requisição |

## Decisões de projeto

| Decisão | Motivo |
|---|---|
| `lifespan` em vez de inicializar o banco no import | O app pode ser importado sem efeitos colaterais; o banco só é criado quando o servidor sobe |
| Sessão de banco por requisição (`SessionDep`) | Ciclo de vida explícito e fechamento garantido |
| Auditoria na mesma transação da operação | O log só existe se a operação foi efetivada |
| Somas de custo em `Decimal` no Python | O SQLite converte `NUMERIC` em ponto flutuante |
| Listagens retornam `{id: manutencao}` | Mantém o contrato usado pelo roteiro original |
| Migrações leves com `ALTER TABLE` | Simplicidade didática; em produção usar Alembic |
| Refresh token opaco, com apenas o hash no banco | Vazamento do banco não expõe tokens válidos |
| Configurações por variáveis de ambiente | Mesmo código em qualquer ambiente, sem segredos no repositório |
