# CLISER DATA NODE — Performance e Capacidade

**Código:** 15.2.9  
**Documento:** Performance e Capacidade  
**Status:** VALIDADO  
**Classificação:** Arquitetura Operacional

---

## 1. Objetivo

Este documento define o modelo de observação, medição e validação de performance e capacidade do CLISER DATA NODE.

O objetivo é estabelecer uma linha de base operacional para:

- execução interna;
- armazenamento de blocos;
- leitura e escrita;
- latência da API;
- API de métricas;
- capacidade lógica;
- capacidade física;
- deduplicação;
- integridade após operações de benchmark.

---

## 2. Escopo

A validação cobre:

1. performance interna;
2. I/O de blocos;
3. latência HTTP;
4. latência da API de métricas;
5. capacidade física e lógica;
6. deduplicação;
7. limpeza de artefatos de benchmark;
8. integridade final.

---

## 3. Baseline Interno

### 3.1 Health

Medição realizada com 10 iterações.

- mínimo: 39.834 ms
- média: 40.149 ms
- mediana: 40.008 ms
- máximo: 41.110 ms

### 3.2 Storage Metrics

Medição realizada com 10 iterações.

- mínimo: 15.104 ms
- média: 15.418 ms
- mediana: 15.274 ms
- máximo: 16.128 ms

---

## 4. Block I/O

Benchmark realizado com blocos de:

- 4 KiB;
- 64 KiB;
- 1 MiB.

### 4.1 4 KiB

- escrita média: 19.960 ms
- leitura média: 3.177 ms
- escrita: 0.196 MB/s
- leitura: 1.230 MB/s

### 4.2 64 KiB

- escrita média: 12.217 ms
- leitura média: 2.003 ms
- escrita: 5.116 MB/s
- leitura: 31.200 MB/s

### 4.3 1 MiB

- escrita média: 13.723 ms
- leitura média: 4.064 ms
- escrita: 72.869 MB/s
- leitura: 246.076 MB/s

A integridade dos dados submetidos ao benchmark foi validada.

---

## 5. API Latency

Benchmark HTTP realizado com 20 iterações por endpoint.

### 5.1 `/health`

- mínimo: 51.273 ms
- média: 60.653 ms
- mediana: 53.894 ms
- máximo: 144.227 ms

### 5.2 `/health/live`

- mínimo: 8.078 ms
- média: 9.494 ms
- mediana: 9.629 ms
- máximo: 11.701 ms

### 5.3 `/health/ready`

- mínimo: 51.598 ms
- média: 58.259 ms
- mediana: 57.290 ms
- máximo: 75.349 ms

---

## 6. Metrics API

Benchmark autenticado realizado com 20 requisições.

Endpoint:

`GET /api/v1/metrics`

Resultados:

- mínimo: 31.961 ms
- média: 40.688 ms
- mediana: 33.177 ms
- máximo: 174.010 ms
- HTTP: 200

A credencial utilizada exclusivamente no benchmark foi posteriormente revogada.

---

## 7. Capacidade Atual

Estado validado após os benchmarks:

- blocos ativos: 48
- blocos únicos: 48
- bytes físicos dos blocos: 9.870.327
- bytes utilizados pelo CLISER: 13.562.950
- capacidade livre do CLISER: 109.846.608.826
- utilização da capacidade CLISER: 0.0123%
- capacidade: NORMAL

---

## 8. Deduplicação

Estado validado:

- razão de deduplicação: 5.9962x
- economia: 49.314.349 bytes
- economia percentual: 83.32%

A deduplicação permanece consistente com as métricas de armazenamento.

---

## 9. Cleanup de Benchmark

O benchmark de Block I/O produziu temporariamente 3 blocos sem referência.

O garbage collector oficial foi executado.

Resultado:

- candidatos: 3
- removidos fisicamente: 3
- registros removidos: 3
- órfãos após limpeza: 0

---

## 10. Integridade Final

Após todos os benchmarks e operações de limpeza:

- Health: HEALTHY
- blocos ativos: 48
- inconsistências: 0
- órfãos: 0
- capacidade: NORMAL
- bytes temporários: 0

A consistência entre Health e Metrics foi validada.

---

## 11. Limitações do Baseline

Este documento representa uma linha de base operacional e não um SLO ou SLA.

Os benchmarks foram executados em ambiente local de desenvolvimento, portanto não representam automaticamente:

- capacidade de produção;
- performance sob concorrência;
- performance em rede externa;
- comportamento sob carga sustentada;
- escalabilidade horizontal;
- comportamento em hardware diferente.

Não foi definido neste estágio um SLO formal de latência ou throughput.

---

## 12. Critérios de Validação

A fase 15.2.9 é considerada validada quando:

- os benchmarks executam sem erro;
- os dados permanecem íntegros;
- artefatos temporários são removidos;
- não existem blocos órfãos;
- métricas permanecem consistentes;
- capacidade permanece em estado NORMAL;
- APIs respondem conforme esperado;
- credenciais temporárias de benchmark são revogadas.

---

## 13. Resultado

**15.2.9 — PERFORMANCE E CAPACIDADE: PASS**

**Integridade operacional: PASS**

**Baseline operacional: ESTABELECIDO**

**Status: CLOSED**
