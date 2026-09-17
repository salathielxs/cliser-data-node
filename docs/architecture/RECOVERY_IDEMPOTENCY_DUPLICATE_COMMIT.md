# CLISER DATA NODE

## 15.2.6-H — Recovery Idempotency & Duplicate Commit Protection

### Objetivo

Validar recuperação idempotente e proteção contra commits duplicados.

### Invariantes

- COMMITTED -> COMPLETE
- COMPLETE não executa novo commit
- FINALIZE produz exatamente um commit
- REVERIFY produz exatamente um commit
- RECOVER produz exatamente um commit
- commit_count permanece 1
- transaction_id permanece estável
- idempotency_key permanece estável
- result_hash permanece estável
- recovery repetido não altera o resultado
- estado committed permanece terminal
