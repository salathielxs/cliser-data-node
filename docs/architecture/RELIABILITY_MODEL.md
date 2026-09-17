# CLISER DATA NODE — RELIABILITY MODEL

**Projeto:** CLISER DATA NODE
**Fase:** 15.2.10 — Reliability
**Documento:** Reliability Model
**Classificação:** Arquitetura / Confiabilidade Operacional
**Status:** CLOSED
**Validação:** 15.2.10-G.14
**Data:** 2026
**Autor:** Salatiel Ribeiro da Hora

---

## 1. Objetivo

Este documento define o modelo de confiabilidade operacional do CLISER DATA NODE.

A camada de Reliability estabelece e valida o comportamento do Node diante de falhas de escrita, falhas transacionais, falhas do banco de dados, interrupções, reinicialização, recuperação, inconsistências Registry/Storage, blocos não referenciados e pressão de capacidade.

As propriedades fundamentais são:

- integridade;
- atomicidade;
- recuperação;
- consistência do Registry;
- consistência Registry/Storage;
- controle de capacidade;
- idempotência de recuperação;
- detecção de estados incompletos;
- limpeza segura de recursos não referenciados;
- preservação dos dados após reinicialização.

---

## 2. Escopo

A arquitetura de confiabilidade abrange:

API / Operational Layer
        |
        v
Object Manager
        |
        +------------------+
        |                  |
        v                  v
Transaction           Allocation
        |                  |
        v                  v
Transaction Journal   Quota / Capacity
        |
        v
Registry / SQLite
        |
        +------------------+
        |                  |
        v                  v
Manifest / Objects       Blocks
        |                  |
        +--------+---------+
                 |
                 v
              Storage

Os mecanismos de Health e Recovery atravessam essas camadas para detectar e tratar estados incompletos.

---

## 3. Modelo de Falha

Os principais cenários considerados são:

- falha antes da escrita;
- escrita parcial;
- falha durante escrita;
- falha durante verificação;
- falha do banco de dados;
- falha após criação de recursos;
- interrupção do processo;
- reinicialização;
- recursos físicos não referenciados;
- exaustão ou pressão de capacidade.

O objetivo é impedir que uma operação parcialmente concluída seja interpretada como uma operação válida.

---

## 4. Máquina de Estados Transacionais

A máquina de estados implementada pelo Node contém:

PREPARED -> WRITING -> VERIFYING -> COMMITTING -> COMMITTED

Em caso de falha:

PREPARED / WRITING / VERIFYING / COMMITTING -> FAILED -> ROLLBACK

Estados terminais:

- COMMITTED
- ROLLBACK

Uma transação FAILED não pode executar commit diretamente.

---

## 5. Transaction Journal

O Transaction Journal registra informações necessárias para determinar o ponto alcançado por uma operação.

São relevantes:

- transaction identity;
- phase;
- resources;
- verification state;
- commit marker;
- rollback state;
- error information.

O modelo diferencia o estado transacional da fase persistida no Journal.

---

## 6. Commit Boundary

A fronteira de commit representa o ponto em que a operação passa de um estado potencialmente recuperável para um estado confirmado.

A sequência operacional validada é:

WRITING -> VERIFYING -> COMMITTING -> COMMIT MARKER -> COMMITTED

O commit marker permite distinguir uma operação que alcançou confirmação de uma operação que foi interrompida antes da confirmação.

---

## 7. Atomicidade

A operação de criação de objeto deve apresentar comportamento atômico: ou os recursos necessários são confirmados de forma consistente, ou os recursos produzidos pela tentativa são revertidos.

O fluxo real de put_object() foi validado para os modos direto e baseado em blocos.

Em caso de exceção, o fluxo executa falha transacional, atualização de estado, remoção dos recursos criados e rollback.

---

## 8. Shared Block Protection

Blocos compartilhados não devem ser removidos durante o rollback de uma operação quando ainda existem referências válidas.

A proteção utiliza a contagem de referências do Registry.

Após operações de limpeza que removem referências diretamente, o modelo exige reconstrução das contagens e execução do mecanismo oficial de Garbage Collection para recursos sem referências.

Invariant:

ref_count == COUNT(manifest_blocks)

Essa invariável foi validada durante a regressão de atomicidade.

---

## 9. Partial Write Protection

Uma escrita parcial não pode ser considerada um bloco válido.

O carregamento de bloco valida:

- existência física;
- status ACTIVE;
- tamanho esperado;
- hash SHA-256;
- correspondência entre conteúdo e registro.

O teste de Partial Write escreveu 1024 bytes para um bloco esperado de 4096 bytes e a leitura foi rejeitada por tamanho inválido.

Resultado: PASS.

---

## 10. Database Failure Detection

O Registry utiliza SQLite como banco operacional.

As verificações de Health detectam exceções de conexão e reportam falha do Registry como estado de erro.

O cenário de falha de banco foi validado por teste controlado de exceção na conexão.

Resultado: Database Failure Detection — PASS.

---

## 11. Transaction Rollback

Quando uma operação transacional falha antes da confirmação, o Node deve retornar os recursos produzidos pela tentativa a um estado consistente.

O fluxo validado é:

FAILED -> state update -> resource cleanup -> ROLLBACK

O rollback foi validado por testes específicos da máquina transacional.

Resultado: Transaction Rollback — PASS.

---

## 12. Real put_object() Atomicity

A função put_object() implementa a fronteira operacional de criação de objetos.

O fluxo validado é:

put_object()
  -> estimate_allocation()
  -> quota check
  -> can_allocate()
  -> transaction
  -> writing
  -> resource creation
  -> verification
  -> commit

Em falha, os recursos criados pela tentativa são removidos conforme o contexto da operação.

Os testes de atomicidade direta, atomicidade baseada em blocos e proteção de blocos compartilhados foram aprovados.

Resultado: Real put_object() Atomicity — PASS.

---

## 13. Recovery Boundaries

O mecanismo de Recovery determina quais estados transacionais podem ser recuperados e quais estados são terminais.

Os estados recuperáveis são tratados separadamente dos estados terminais.

A recuperação deve preservar a identidade da transação e produzir resultado estável quando executada novamente.

Foram executados 19 testes relacionados a transaction recovery, recovery idempotency e persistent restart recovery.

Resultado: Recovery Boundaries — PASS.

---

## 14. Restart Recovery

A arquitetura suporta recuperação após reinicialização do processo.

Durante a inicialização, estados transacionais incompletos podem ser identificados e processados conforme as regras de Recovery.

A validação incluiu cenários persistentes executados em processos separados.

Resultado: Restart Recovery — PASS.

---

## 15. Durability

O Registry utiliza SQLite com os seguintes parâmetros observados em runtime:

- journal_mode = delete;
- synchronous = 2 (FULL);
- foreign_keys = 1;
- locking_mode = normal.

Esses parâmetros fornecem a base de durabilidade transacional do SQLite utilizada pelo Node.

Foi validada a persistência física de um bloco entre processos independentes.

Resultado: Physical Restart Durability — PASS.

Limitação: não foi evidenciada implementação explícita de fsync(), fdatasync() ou flush() no código Python de Storage.

Portanto, o modelo não declara garantia adicional de persistência física além daquela fornecida pelo sistema de arquivos e pelo SQLite nas condições observadas.

---

## 16. Capacity / Disk Exhaustion

O módulo de Capacity protege o Node contra alocações incompatíveis com a capacidade disponível.

Os estados operacionais validados são:

- NORMAL;
- WARNING;
- CRITICAL;
- READ_ONLY.

Os limites testados foram:

- WARNING: 5 GiB;
- CRITICAL: 1 GiB;
- READ_ONLY: 512 MiB.

O fluxo operacional de put_object() estima a alocação física, verifica quota e executa can_allocate() antes da criação dos recursos.

Resultado: Capacity / Disk Exhaustion — PASS.

---

## 17. Garbage Collection

O Garbage Collection remove blocos físicos que não possuem referências válidas.

O mecanismo oficial garbage_collect_blocks() realiza a limpeza física e a limpeza correspondente do Registry.

A validação da fase demonstrou que a remoção de referências deve ser seguida pela reconstrução dos ref_counts quando necessário e pelo GC oficial.

Estado final validado: zero blocos órfãos.

---

## 18. Reliability Health Model

O Health Model consolida os principais indicadores de confiabilidade operacional.

São considerados:

- integridade dos blocos;
- blocos órfãos;
- capacidade;
- transações pendentes;
- inconsistências do Journal;
- inconsistências de ref_count;
- estado do Registry.

Uma condição HEALTHY exige consistência entre esses componentes.

---

## 19. Reliability Test Matrix

A matriz de testes da fase 15.2.10 cobre:

- Partial Write;
- Disk Exhaustion;
- Database Failure Detection;
- Transaction Rollback;
- Real put_object() Atomicity;
- Recovery Boundaries;
- Restart Recovery;
- Physical Restart Durability;
- Atomicity;
- Recovery Idempotency.

Os testes específicos foram executados com sucesso.

---

## 20. Final Reliability Regression

A regressão final da fase 15.2.10-G.14 executou 30 testes.

Resultado:

30 passed in 4.85s

Health final: HEALTHY.

---

## 21. Final Operational State

Estado operacional validado após a regressão final:

- ACTIVE BLOCKS: 53;
- INTEGRITY MISMATCHES: 0;
- ORPHANS: 0;
- CAPACITY STATE: NORMAL;
- PENDING TRANSACTIONS: 0;
- JOURNAL PENDING: 0;
- JOURNAL INCONSISTENT: 0;
- REFCOUNT MISMATCHES: 0.

Todos os indicadores finais de confiabilidade apresentaram estado consistente.

---

## 22. Reliability Classification

A fase 15.2.10 foi validada operacionalmente com os mecanismos de confiabilidade identificados e testados neste documento.

Classificação da fase: CLOSED.

---

## 23. Limitations

As seguintes limitações permanecem explicitamente registradas:

- não foi evidenciada chamada explícita a fsync();
- não foi evidenciada chamada explícita a fdatasync();
- não foi evidenciada chamada explícita a flush() no Storage Python;
- não é declarada garantia adicional contra perda física de energia além das garantias observadas do sistema de arquivos e SQLite;
- o modo SQLite observado utiliza journal_mode=delete, e não WAL.

Essas limitações não invalidam os testes de durabilidade realizados, mas delimitam a garantia que pode ser formalmente declarada.

---

## 24. Acceptance Criteria

Os critérios de aceitação da Reliability são:

- escrita parcial rejeitada;
- falha de banco detectada;
- rollback transacional validado;
- atomicidade real validada;
- recovery validado;
- recovery idempotente validado;
- restart recovery validado;
- durabilidade física entre processos validada;
- proteção de blocos compartilhados validada;
- limites de capacidade validados;
- Garbage Collection validado;
- Health final HEALTHY;
- zero inconsistências de ref_count;
- zero órfãos;
- regressão final aprovada.

Resultado: TODOS OS CRITÉRIOS ATENDIDOS.

---

## 25. Formal Closure

A fase 15.2.10 — Reliability é considerada formalmente encerrada após a validação documental e a confirmação do estado operacional final do Node.

Critérios finais de fechamento:

- documentação presente;
- seções arquiteturais completas;
- regressão final aprovada;
- Health HEALTHY;
- integridade sem inconsistências;
- zero órfãos;
- capacidade NORMAL;
- zero transações pendentes;
- Journal sem pendências ou inconsistências;
- ref_count consistente.

Resultado esperado do fechamento: 15.2.10 — CLOSED.

---

## 26. Document Control

**Documento:** RELIABILITY_MODEL.md
**Projeto:** CLISER DATA NODE
**Fase:** 15.2.10
**Área:** Reliability
**Validação técnica:** 15.2.10-G.14
**Validação documental:** 15.2.10-H.1 — PASS
**Estado operacional registrado:** HEALTHY
**Classificação:** Arquitetura / Confiabilidade Operacional
**Autor:** Salatiel Ribeiro da Hora
**Ano:** 2026

Este documento registra a arquitetura, os mecanismos, as limitações conhecidas, os testes e o estado de validação da confiabilidade do CLISER DATA NODE.

Fim do documento.

### Formal Closure Record

**Document Validation:** PASS
**Operational Integrity:** PASS
**Technical Regression:** 30/30 PASS
**Reliability Phase:** CLOSED

The 15.2.10 Reliability phase has completed its technical, operational, and documentary validation.
