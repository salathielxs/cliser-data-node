# CLISER DATA NODE
# 16.4-C.7-A — REPLAY LIFECYCLE SPECIFICATION

Status: SPECIFICATION
Generated at: 2026-09-17T22:51:09.880329+00:00

---

## 1. OBJECTIVE

Formalizar o lifecycle dos registros de replay do transporte
antes da implementação da expiração lógica e do cleanup físico.

O mecanismo protege o Data Node contra reutilização de um
CellEnvelope dentro da janela de replay.

---

## 2. REPLAY IDENTITY

A identidade primária do replay é:

    envelope_id

O envelope_id é utilizado porque:

- identifica exclusivamente o CellEnvelope;
- participa do payload assinado;
- está criptograficamente vinculado à assinatura;
- possui PRIMARY KEY em replay_records.

request_id NÃO é utilizado como identidade primária do replay.

---

## 3. REPLAY WINDOW

A janela nominal atual é:

    60 segundos

A origem temporal da expiração é:

    envelope.timestamp

A expiração nominal é:

    expires_at = envelope.timestamp + 60 seconds

A validação de freshness ocorre antes da reserva de replay.

---

## 4. TIMESTAMPS

### received_at

Representa o instante em que o Data Node recebeu/processou
a tentativa de reserva.

Fonte:

    datetime.now(timezone.utc)

### expires_at

Representa o limite temporal até o qual o envelope permanece
protegido contra replay.

Fonte lógica:

    envelope.timestamp + 60 seconds

Ambos devem permanecer em UTC e em formato ISO-8601.

---

## 5. CURRENT PIPELINE

A ordem atualmente implementada é:

    verify_signature()
        |
        v
    validate_freshness()
        |
        v
    reserve_replay()
        |
        v
    identity / authorization
        |
        v
    permission
        |
        v
    execute_request()

Essa ordem não deve ser alterada incidentalmente durante
a implementação do lifecycle.

---

## 6. VALID RECORD

Se existir um registro cujo expires_at ainda não tenha passado:

    mesmo envelope_id
        |
        v
    REPLAY BLOCK

Resultado esperado:

    reserve -> False

---

## 7. EXPIRED RECORD

Se existir um registro cujo expires_at já tenha passado:

    envelope_id existente
        +
    expires_at < current_time
        |
        v
    registro expirado

Política especificada:

    o registro expirado pode deixar de bloquear uma
    nova reserva do mesmo envelope_id somente se a
    substituição ocorrer atomicamente.

Não deve existir uma janela DELETE -> INSERT exposta
a concorrência.

---

## 8. ATOMIC RENEWAL

A renovação de um registro expirado deve obedecer:

    expired record
        |
        v
    atomic replacement
        |
        v
    exactly one winner

Para N processos concorrentes tentando renovar o mesmo
envelope_id:

    exactly 1 -> accepted
    N-1      -> rejected as replay/concurrency conflict

A PRIMARY KEY(envelope_id) deve continuar sendo uma
invariante estrutural.

---

## 9. NEW ENVELOPE

Para um envelope_id inexistente:

    INSERT
        |
        v
    accepted

Resultado:

    True

---

## 10. CLEANUP

Cleanup físico é separado do enforcement.

### Enforcement

Responsável por decidir se o envelope pode ser reservado.

### Cleanup

Responsável por remover registros expirados que já não
precisam permanecer no banco.

O funcionamento do enforcement NÃO deve depender da execução
prévia de um processo de cleanup.

Portanto:

    cleanup ausente
        !=
    replay protection ausente

---

## 11. CLEANUP SAFETY

O cleanup deve remover somente registros cuja condição seja:

    expires_at < current_time

Registros ainda válidos não podem ser removidos.

O cleanup deve ser idempotente:

    executar uma vez   -> remove expirados
    executar novamente -> nenhum efeito indevido

---

## 12. AUTHORIZATION BOUNDARY

A implementação atual reserva o envelope antes da resolução
completa de identidade/autorização.

Isso significa que uma tentativa que falhe posteriormente
pode consumir a identidade de replay.

Essa semântica é registrada como decisão arquitetural a ser
testada, não alterada silenciosamente.

Qualquer mudança dessa ordem exige teste específico.

---

## 13. SECURITY INVARIANTS

As seguintes invariantes devem permanecer verdadeiras:

### INV-01

Um CellEnvelope válido não pode ser executado duas vezes
dentro da sua janela de replay.

### INV-02

Dois processos concorrentes não podem obter simultaneamente
a reserva do mesmo envelope_id.

### INV-03

Um registro expirado não deve bloquear indefinidamente
o lifecycle do sistema.

### INV-04

A existência de cleanup não pode ser requisito para que
o enforcement funcione corretamente.

### INV-05

A assinatura continua sendo validada antes da reserva.

### INV-06

Freshness continua sendo validada antes da reserva.

### INV-07

A identidade envelope_id continua vinculada
criptograficamente ao CellEnvelope.

### INV-08

A operação de lifecycle não deve permitir duplicidade
de registros para o mesmo envelope_id.

---

## 14. FAILURE MODEL

A implementação deverá considerar:

- dois processos tentando reservar simultaneamente;
- dois processos tentando renovar registro expirado;
- registro válido;
- registro expirado;
- envelope inexistente;
- falha de autorização após reserva;
- falha de permission check após reserva;
- reinício do processo;
- nova conexão SQLite;
- cleanup concorrente com reserva.

---

## 15. CURRENT FORENSIC EVIDENCE

### 16.4-C.5-A

Replay persistence:

    PASS

### 16.4-C.5-C

Functional replay:

    PASS

### 16.4-C.6-B

Expired record remained blocking:

    GAP CONFIRMED

### 16.4-C.6-C

Lifecycle policy gap:

    CONFIRMED

### 16.4-C.6-E

Eight concurrent reservations:

    1 accepted
    7 rejected
    0 errors
    1 database record

Concurrency invariant:

    PASS

---

## 16. NEXT IMPLEMENTATION

The next implementation stage shall address:

    16.4-C.7-B

Expected implementation responsibilities:

1. expiration-aware replay reservation;
2. atomic handling of expired records;
3. preservation of concurrency guarantees;
4. independent expired-record cleanup;
5. regression tests for existing replay behavior.

Production code must not be modified until the implementation
is backed by isolated tests.

---

## STATUS

16.4-C.7-A — SPECIFICATION GENERATED

Status:

    CLOSED — SPECIFICATION READY

Next:

    16.4-C.7-B — EXPIRATION-AWARE RESERVATION DESIGN
