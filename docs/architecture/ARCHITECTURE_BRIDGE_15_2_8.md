# CLISER DATA NODE — ARCHITECTURE BRIDGE

**Código:** 15.2.8  
**Status:** DRAFT  
**Objetivo:** Formalizar a fronteira entre Control Plane, API Layer e Data Plane / Node Core.

## 1. Objetivo

Esta fase define as fronteiras arquiteturais entre:

- Control Plane
- API Layer
- Data Plane / Node Core
- Persistent Storage

Nenhum novo serviço ou módulo é criado nesta fase.

## 2. Arquitetura

CLIENT / OPERATOR
        |
        v
CONTROL PLANE
        |
        v
API LAYER
FastAPI / HTTP
        |
        v
NODE CORE / DATA PLANE
        |
        +----------------+
        |                |
        v                v
    Registry        Transaction
        |                |
        +-------+--------+
                |
                v
       PERSISTENT STORAGE
          SQLite / Files

## 3. Control Plane

Representa operações administrativas e de gerenciamento do node.

Responsabilidades:

- configuração
- políticas
- quotas
- lifecycle
- observabilidade
- administração
- manutenção
- controle operacional

Não deve manipular diretamente arquivos físicos.

## 4. API Layer

Representa a fronteira de exposição do node.

Responsabilidades:

- autenticação
- autorização
- validação
- tratamento de erros
- rate limiting
- idempotência
- HTTP
- encaminhamento ao Node Core

A API Layer não é o armazenamento.

## 5. Data Plane / Node Core

Representa a execução das operações de dados.

Módulos:

- Access Control
- Accounting
- Allocation
- Block Management
- Capacity
- Identity
- Lifecycle
- Manifest
- Namespace
- Object
- Quota
- Recovery
- Registry
- Storage
- Transaction
- Integrity

## 6. Persistent Storage

Representa o estado durável do node.

Inclui:

- SQLite
- objetos
- blocos
- manifests
- journal
- estruturas persistentes autorizadas pelo Registry

## 7. Boundary Rules

### Control Plane

Pode solicitar operações administrativas e consultar estado operacional.

Não pode:

- ignorar autenticação
- ignorar autorização
- modificar storage diretamente
- contornar transactions
- contornar integrity checks

### API Layer

Pode:

- receber requisições
- autenticar
- autorizar
- validar
- encaminhar operações

Não pode modificar arquivos físicos diretamente.

### Node Core

Pode:

- executar operações de dados
- controlar transactions
- executar recovery
- controlar registry
- controlar storage
- validar integridade

### Storage

Deve:

- persistir estado autorizado
- permanecer consistente com Registry
- obedecer às regras de integridade
- participar dos mecanismos transacionais aplicáveis

## 8. Transaction Boundary

Toda operação que modifica estado persistente deve respeitar:

- transaction
- journal
- commit
- rollback
- recovery
- idempotency
- integrity

Nenhuma nova camada deve contornar esses mecanismos.

## 9. Security Boundary

Todas as interfaces devem respeitar:

- identity
- authentication
- authorization
- permissions
- namespace isolation
- credential controls
- integrity controls

## 10. Observability

A observabilidade deve distinguir:

- requisições API
- operações administrativas
- operações de dados
- transactions
- recovery
- storage
- erros
- métricas

## 11. Non-Goals

Esta fase NÃO implementa:

- novo servidor
- novo serviço
- novo banco
- novo Control Plane
- nova API
- novo protocolo
- alteração do modelo transacional
- alteração do storage

## 12. Relationship With Previous Phases

### 15.2.6 — Transaction & Recovery

Define as garantias transacionais e de recuperação utilizadas pelo Node Core.

### 15.2.7 — Security

Define os controles de segurança aplicáveis às interfaces e operações.

### 15.2.8 — Architecture Bridge

Define as fronteiras entre Control Plane, API Layer e Data Plane.

### 15.2.9 — Performance & Capacity

Avalia desempenho e capacidade das interfaces e operações existentes.

## 13. Validation Criteria

A fase 15.2.8 poderá ser considerada validada quando:

1. API Layer estiver delimitada.
2. Node Core / Data Plane estiver delimitado.
3. Control Plane estiver definido conceitualmente.
4. Persistent Storage estiver delimitado.
5. não existir caminho documentado que contorne Transaction.
6. não existir caminho documentado que contorne Security.
7. responsabilidades estiverem atribuídas.
8. 15.2.6 -> 15.2.7 -> 15.2.8 -> 15.2.9 estiver documentado.

## 14. Status

**15.2.8 — ARCHITECTURE BRIDGE: DRAFT**

Nenhuma implementação foi realizada nesta fase.
