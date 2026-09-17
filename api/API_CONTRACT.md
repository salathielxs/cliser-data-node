# CLISER DATA NODE
# API CONTRACT — v1

Status: INTERNAL
Version: 1.0
Architecture: CLISER DATA NODE
API Base: /api/v1

---

# 1. PRINCÍPIOS

A API é uma camada de exposição do Node Core.

A API NÃO implementa diretamente:

- armazenamento físico;
- gerenciamento de blocos;
- manifests;
- transações;
- quotas;
- garbage collection;
- criptografia de identidade.

Essas funções permanecem no Node Core.

Fluxo:

CLIENT
  ↓
API
  ↓
AUTHENTICATION
  ↓
AUTHORIZATION
  ↓
VALIDATION
  ↓
SERVICE
  ↓
NODE CORE
  ↓
REGISTRY / STORAGE

---

# 2. BASE URL

/api/v1

---

# 3. FORMATO

Request:

Content-Type: application/json

Response:

Content-Type: application/json

Binary object download:

Content-Type: application/octet-stream

---

# 4. REQUEST ID

Toda requisição recebe:

X-Request-ID

Se o cliente fornecer um Request ID válido, a API poderá reutilizá-lo.

O Request ID deve aparecer em:

- logs;
- erros;
- transações relacionadas;
- resposta HTTP.

---

# 5. AUTENTICAÇÃO

Rotas protegidas exigem identidade autenticada.

Header inicial:

Authorization: Bearer <credential>

A implementação da credencial será definida na camada de autenticação.

A API nunca deve registrar:

- senha;
- chave privada;
- token completo;
- material criptográfico secreto.

---

# 6. AUTORIZAÇÃO

A autorização utiliza o modelo existente:

ADMIN
OWNER
WRITER
READER

Permissões existentes:

object.create
object.read
object.delete
object.sign

namespace.read
namespace.manage

quota.manage
node.manage

A API não deve criar um sistema paralelo de permissões.

---

# 7. NAMESPACE

## POST /namespaces

Cria namespace.

Permissão:

namespace.manage

Request:

{
  "namespace": "example",
  "quota_bytes": 0
}

Response:

201 Created

{
  "namespace": "example",
  "status": "ACTIVE",
  "quota_bytes": 0
}

---

## GET /namespaces

Lista namespaces acessíveis.

Permissão:

namespace.read

Response:

200 OK

{
  "items": []
}

---

## GET /namespaces/{namespace}

Consulta namespace.

Permissão:

namespace.read

---

## PATCH /namespaces/{namespace}

Altera estado/configuração administrativa.

Permissão:

namespace.manage

---

## DELETE /namespaces/{namespace}

Operação administrativa.

Permissão:

namespace.manage

---

# 8. OBJECTS

## POST /objects

Cria objeto.

Permissão:

object.create

Request conceitual:

{
  "namespace": "default",
  "content": "<binary>"
}

A implementação poderá utilizar multipart/form-data ou streaming.

Fluxo obrigatório:

validation
→ authorization
→ quota
→ allocation
→ transaction
→ storage
→ verification
→ commit

Response:

201 Created

{
  "object_id": "...",
  "namespace": "default",
  "size": 12345,
  "content_hash": "...",
  "status": "ACTIVE"
}

---

## GET /objects/{object_id}

Retorna conteúdo do objeto.

Permissão:

object.read

Response:

200 OK

Content-Type:

application/octet-stream

---

## HEAD /objects/{object_id}

Retorna somente metadados HTTP.

Permissão:

object.read

---

## GET /objects/{object_id}/metadata

Retorna metadados.

Permissão:

object.read

Response:

{
  "object_id": "...",
  "namespace": "default",
  "content_hash": "...",
  "size": 12345,
  "status": "ACTIVE",
  "created_at": "..."
}

---

## GET /objects/{object_id}/integrity

Executa/verifica integridade lógica do objeto.

Permissão:

object.read

Response:

{
  "object_id": "...",
  "valid": true,
  "content_hash": "...",
  "size": 12345
}

---

## GET /objects/{object_id}/manifest

Retorna estrutura do objeto em blocos.

Permissão:

object.read

Response:

{
  "object_id": "...",
  "block_size": 1048576,
  "block_count": 4,
  "total_size": 4194304,
  "blocks": []
}

---

## DELETE /objects/{object_id}

Remove logicamente o objeto.

Permissão:

object.delete

Fluxo:

authorization
→ transaction
→ soft delete
→ commit

A remoção física poderá ocorrer posteriormente pelo lifecycle/GC.

Response:

204 No Content

---

# 9. BLOCKS

Blocos são recursos internos.

Clientes comuns NÃO podem escrever blocos diretamente.

## GET /blocks/{block_id}

Permissão:

node.manage

Retorna metadados administrativos do bloco.

---

## GET /blocks/{block_id}/integrity

Permissão:

node.manage

Response:

{
  "block_id": "...",
  "content_hash": "...",
  "size": 12345,
  "valid": true
}

---

# 10. TRANSACTIONS

## GET /transactions

Lista transações visíveis ao administrador.

Permissão:

node.manage

---

## GET /transactions/{transaction_id}

Consulta uma transação.

Permissão:

node.manage

Response:

{
  "transaction_id": "...",
  "object_id": "...",
  "namespace": "...",
  "operation": "...",
  "state": "COMMITTED",
  "created_at": "...",
  "updated_at": "..."
}

---

# 11. QUOTAS

## GET /namespaces/{namespace}/quota

Consulta quota.

Permissão:

namespace.read

Response:

{
  "namespace": "default",
  "quota_bytes": 1073741824,
  "used_bytes": 123456,
  "available_bytes": 1072518526
}

---

## PUT /namespaces/{namespace}/quota

Define quota.

Permissão:

quota.manage

Request:

{
  "quota_bytes": 1073741824,
  "mode": "LOGICAL"
}

Modos:

LOGICAL
PHYSICAL
HYBRID

---

# 12. HEALTH

## GET /health

Endpoint público de saúde básica do serviço.

Response:

200 OK

{
  "status": "healthy"
}

Se o serviço estiver indisponível:

503 Service Unavailable

---

## GET /health/live

Verifica se o processo está ativo.

Não deve depender do storage completo.

---

## GET /health/ready

Verifica se o nó está pronto para receber operações.

Deve considerar:

- registry;
- storage;
- identity;
- transaction subsystem;
- journal;
- capacidade.

---

# 13. METRICS

## GET /metrics

Permissão:

node.manage

Retorna métricas do nó.

Estrutura conceitual:

{
  "objects": {},
  "blocks": {},
  "storage": {},
  "transactions": {},
  "quotas": {},
  "deduplication": {}
}

---

# 14. IDENTITY

## GET /identity

Retorna somente informações públicas da identidade.

Nunca retorna:

- private key;
- protected private key;
- password;
- secret material.

Response:

{
  "identity_id": "...",
  "algorithm": "Ed25519",
  "fingerprint": "..."
}

Permissão:

node.manage

---

# 15. LIFECYCLE

Rotas administrativas.

## POST /lifecycle/gc

Executa garbage collection.

Permissão:

node.manage

---

## POST /lifecycle/rebuild-refcounts

Reconstrói contadores de referência.

Permissão:

node.manage

---

## POST /lifecycle/integrity-check

Executa verificação global.

Permissão:

node.manage

---

# 16. NODE

## GET /node

Informações gerais do nó.

Permissão:

node.manage

Response:

{
  "node": "CLISER DATA NODE",
  "version": "...",
  "status": "READY"
}

---

# 17. PAGINAÇÃO

Listagens utilizarão:

limit
cursor

Exemplo:

GET /objects?namespace=default&limit=50

Response:

{
  "items": [],
  "next_cursor": null
}

---

# 18. ERRO PADRÃO

Todas as falhas de API devem seguir:

{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "request_id": "...",
    "details": {}
  }
}

---

# 19. CÓDIGOS DE ERRO

AUTH_REQUIRED
AUTH_INVALID

ACCESS_DENIED

NAMESPACE_NOT_FOUND
NAMESPACE_DISABLED
NAMESPACE_INVALID

OBJECT_NOT_FOUND
OBJECT_INTEGRITY_ERROR

BLOCK_NOT_FOUND
BLOCK_INTEGRITY_ERROR

QUOTA_NOT_CONFIGURED
QUOTA_EXCEEDED

CAPACITY_EXCEEDED

INVALID_REQUEST
INVALID_CONTENT
PAYLOAD_TOO_LARGE

TRANSACTION_FAILED
TRANSACTION_PENDING

STORAGE_ERROR
REGISTRY_ERROR

INTERNAL_ERROR

---

# 20. HTTP STATUS

200 OK
201 Created
202 Accepted
204 No Content

400 Bad Request
401 Unauthorized
403 Forbidden
404 Not Found
409 Conflict
413 Payload Too Large
422 Unprocessable Entity
429 Too Many Requests

500 Internal Server Error
503 Service Unavailable

---

# 21. IDEMPOTÊNCIA

Operações mutáveis poderão aceitar:

Idempotency-Key

Exemplo:

POST /objects

Idempotency-Key: <unique-key>

A mesma operação não deve criar múltiplos objetos por repetição acidental da requisição.

A implementação será integrada ao transaction subsystem.

---

# 22. LIMITES

A API deve possuir limites configuráveis para:

- tamanho máximo de request;
- tamanho máximo de objeto;
- número de requests;
- timeout;
- número de operações concorrentes;
- paginação.

Os limites não devem substituir quota ou capacity.

---

# 23. SEGURANÇA

A API deve:

- validar entrada;
- validar namespace;
- autenticar identidade;
- autorizar operação;
- respeitar quota;
- respeitar capacity;
- utilizar transaction subsystem;
- verificar integridade;
- gerar request_id;
- evitar exposição de segredos;
- evitar path traversal;
- evitar acesso direto ao filesystem;
- evitar escrita direta no SQLite por rotas;
- evitar bypass do Node Core.

---

# 24. ARQUITETURA DE DEPENDÊNCIAS

API:

api/routes
   ↓
api/services
   ↓
node/*
   ↓
registry/storage

Nunca:

api/routes
   ↓
SQLite diretamente

ou:

api/routes
   ↓
filesystem diretamente

---

# 25. VERSIONAMENTO

Versão inicial:

/api/v1

Mudanças incompatíveis deverão utilizar:

/api/v2

Alterações compatíveis permanecem em:

/api/v1

---

# 26. ORDEM DE IMPLEMENTAÇÃO

14.1 Contrato
14.2 Estrutura API
14.3 HTTP server
14.4 Authentication
14.5 Authorization
14.6 Namespace
14.7 Object
14.8 Upload
14.9 Download
14.10 Metadata
14.11 Manifest
14.12 Transactions
14.13 Quota
14.14 Health
14.15 Metrics
14.16 Lifecycle
14.17 Idempotency
14.18 Limits
14.19 Rate limiting
14.20 Error handling
14.21 Request ID
14.22 Logging
14.23 OpenAPI
14.24 API tests
14.25 Final audit

---

# 27. REGRA PRINCIPAL

A API nunca deve ser capaz de criar um caminho alternativo que contorne:

Authentication
Authorization
Quota
Allocation
Transaction
Verification
Commit
Integrity

O Node Core continua sendo a autoridade do CLISER DATA NODE.
