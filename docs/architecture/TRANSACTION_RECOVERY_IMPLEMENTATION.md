# CLISER DATA NODE
# 15.2.6-F — TRANSACTION RECOVERY IMPLEMENTATION

## Objetivo

Implementar o mecanismo de recuperação de transações interrompidas
durante WRITE, VERIFY e COMMIT.

## Componentes

### Recovery Engine

Arquivo:

scripts/transaction_recovery_engine.py

Responsabilidades:

- carregar transaction journal;
- inspecionar estado;
- determinar ação de recovery;
- executar recovery;
- persistir novo estado;
- evitar commit duplicado;
- finalizar commit previamente persistido;
- executar rollback;
- colocar estados desconhecidos em quarantine.

## Recovery Actions

- RECOVER
- REVERIFY
- FINALIZE
- ROLLBACK
- QUARANTINE
- COMPLETE

## Recovery States

- NEW
- PREPARED
- WRITING
- VERIFYING
- COMMITTING
- COMMITTED
- ROLLED_BACK
- RECOVERABLE
- IN_DOUBT
- CORRUPTED
- QUARANTINED

## Atomic Journal Write

O journal utiliza arquivo temporário seguido de os.replace().

Isso evita deixar o arquivo principal parcialmente escrito.

## Idempotência

Cada transação possui:

transaction_id
idempotency_key

O recovery deve verificar se o commit já foi persistido antes
de executar novamente uma operação.

## Rollback

Rollback é utilizado para:

- PREPARED interrompido;
- WRITE incompleto;
- verification failure;
- estado inválido.

## Commit Recovery

Se COMMITTING for encontrado após restart:

1. carregar journal;
2. verificar estado persistido;
3. verificar transaction_id;
4. verificar idempotency;
5. verificar hashes;
6. finalizar ou recuperar;
7. nunca executar commit cegamente.

## Quarantine

Estados inconsistentes ou não reconhecidos são enviados para:

QUARANTINED

Não devem ser automaticamente modificados.

## Testes

Arquivo:

tests/test_transaction_recovery.py

Cenários:

1. PREPARED -> ROLLBACK
2. WRITING incompleto -> ROLLBACK
3. VERIFYING interrompido -> REVERIFY
4. COMMITTING já persistido -> FINALIZE
5. COMMITTED -> COMPLETE
6. Verification failure -> ROLLBACK
7. IN_DOUBT -> QUARANTINE

## Critério

15.2.6-F passa quando todos os testes forem aprovados.
