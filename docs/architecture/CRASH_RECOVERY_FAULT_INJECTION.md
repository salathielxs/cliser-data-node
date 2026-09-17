# CLISER DATA NODE

# 15.2.6-G — CRASH RECOVERY & FAULT INJECTION

## Objetivo

Validar o comportamento do Transaction Recovery Engine quando
uma transação sofre uma interrupção artificial em diferentes
pontos do lifecycle.

## Fault Points

### AFTER_PREPARED

Simula crash imediatamente após PREPARED.

Esperado:

PREPARED -> ROLLBACK

### DURING_WRITE

Simula interrupção durante WRITE.

Esperado:

WRITING incompleto -> ROLLBACK

### AFTER_WRITE

Simula crash após WRITE completo e antes da conclusão da verificação.

Esperado:

REVERIFY -> COMMITTED

### DURING_VERIFY

Simula interrupção durante VERIFY.

Esperado:

REVERIFY -> COMMITTED

### AFTER_VERIFY

Simula crash após verification concluída e antes de COMMIT.

Esperado:

RECOVER -> COMMITTED

### DURING_COMMIT

Simula interrupção após COMMIT iniciado, mas antes da persistência.

Esperado:

RECOVER -> COMMITTED

### AFTER_COMMIT

Simula interrupção após persistência do commit, mas antes do
marcador final de conclusão.

Esperado:

FINALIZE -> COMMITTED

## No Fault

Uma transação sem falha deve produzir:

NEW
 ->
PREPARED
 ->
WRITING
 ->
VERIFYING
 ->
COMMITTING
 ->
COMMITTED

## Invariantes

1. Uma transação não pode ser COMMITTED duas vezes.
2. Uma transação parcialmente escrita não deve ser considerada
   COMMITTED.
3. Uma transação com commit persistido deve ser finalizada.
4. Recovery deve ser idempotente.
5. O journal deve sobreviver ao restart.
6. Falhas devem produzir estado determinístico.
7. Estados desconhecidos devem ser isolados.
8. Nenhuma operação de commit deve ser repetida cegamente.

## Resultado

A etapa 15.2.6-G será considerada válida quando:

- todos os fault points forem executados;
- todos os testes passarem;
- cada crash possuir ação de recovery determinística;
- nenhuma transação terminar em estado inconsistente.
