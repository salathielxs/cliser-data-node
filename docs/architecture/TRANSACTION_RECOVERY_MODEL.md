# CLISER DATA NODE

# Transaction & Recovery Model — 15.2.6

**Status:** AUDITED BASELINE
**Phase:** 15.2.6
**Scope:** Transaction lifecycle, crash recovery, idempotency and persistent restart recovery.

---

## 1. Purpose

This document defines the transaction and recovery model currently implemented and validated in the CLISER DATA NODE.

The model covers:

- transaction lifecycle;
- persistent transaction state;
- state transition validation;
- recovery decisions;
- crash/fault injection;
- rollback;
- re-verification;
- commit recovery;
- idempotent recovery;
- duplicate commit protection;
- persistent journal;
- restart recovery.

---

## 2. Transaction State Model

Current transaction states:

```text
NEW
PREPARED
WRITING
VERIFYING
COMMITTING
COMMITTED
ROLLED_BACK
QUARANTINED
```

Normal lifecycle:

```text
NEW
 │
 ▼
PREPARED
 │
 ▼
WRITING
 │
 ▼
VERIFYING
 │
 ▼
COMMITTING
 │
 ▼
COMMITTED
```


---

## 3. State Semantics

### NEW

Initial transaction state.

Characteristics:

- transaction identity exists;
- no transactional work has started;
- no write operation is active;
- transaction may proceed to `PREPARED`.

### PREPARED

Transaction has been prepared for execution.

Characteristics:

- transaction metadata is established;
- payload identity is known;
- transaction is recoverable;
- interruption at this point must not produce a commit.

Recovery:

```text
PREPARED → ROLLED_BACK
```

### WRITING

Persistent write operation has started.

Characteristics:

- write operation has begun;
- partial or complete write may exist;
- recovery cannot assume that the write is complete.

Recovery:

```text
WRITING → ROLLED_BACK
```

### VERIFYING

The write has completed and verification is being performed.

Characteristics:

- written data exists;
- integrity verification is active;
- commit has not yet occurred.

Recovery:

```text
VERIFYING → REVERIFY
```

Successful re-verification may continue to commit recovery.

### COMMITTING

The transaction has entered the commit phase.

Characteristics:

- commit intent is persisted;
- recovery must distinguish between incomplete and completed commit;
- duplicate commit must be prevented.

Recovery:

```text
COMMITTING → RECOVER
```

### COMMITTED

Transaction has reached its final successful state.

Characteristics:

- commit is complete;
- result identity must remain stable;
- recovery is idempotent;
- a second recovery must not create another commit.

Recovery:

```text
COMMITTED → COMPLETE
```

### ROLLED_BACK

Transaction has been rolled back.

Characteristics:

- transactional execution is no longer considered successful;
- no commit may be generated from the original transaction.

### QUARANTINED

Transaction requires isolation from normal processing.

Characteristics:

- recovery cannot safely determine a valid continuation;
- transaction is removed from normal execution;
- manual or higher-level investigation may be required.

---

## 4. Persistent Journal

The transaction journal is the persistent recovery source.

Its purpose is to preserve enough transaction state to reconstruct the transaction after process termination.

The journal contains the serialized transaction object, including:

- `transaction_id`;
- `idempotency_key`;
- `state`;
- `payload_hash`;
- `result_hash`;
- write status;
- verification status;
- commit status;
- persistence status;
- recovery count;
- error information.

The journal is written atomically using the following conceptual sequence:

```text
Transaction State
       │
       ▼
Temporary Journal File
       │
       ▼
flush()
       │
       ▼
fsync()
       │
       ▼
atomic replace
       │
       ▼
Persistent Journal
```

The implementation uses a temporary file followed by `os.replace()`.

This prevents a normal journal update from directly overwriting the active journal with an incompletely written JSON document.


---

## 5. Recovery Decision Model

Recovery is determined from the last durable transaction state recorded in the journal.

The recovery engine must not infer success solely from process termination.

Decision model:

```text
Persisted State
      │
      ▼
Recovery Decision
      │
      ├── PREPARED ───────→ ROLLBACK
      │
      ├── WRITING ────────→ ROLLBACK
      │
      ├── VERIFYING ──────→ REVERIFY
      │
      ├── COMMITTING ─────→ RECOVER
      │
      ├── COMMITTED ──────→ COMPLETE
      │
      ├── ROLLED_BACK ────→ terminal recovery handling
      │
      └── UNKNOWN ─────────→ QUARANTINE
```

Recovery decisions are based on durable transaction evidence rather than assumptions about where the process stopped.

## 6. Recovery Actions

The recovery engine defines the following actions:

### NONE

No recovery operation is required.

### ROLLBACK

Reverses an incomplete transaction that has not reached a valid commit phase.

Primary states:

- `PREPARED`;
- `WRITING`.

### REVERIFY

Re-executes verification against persisted write state before allowing commit recovery.

Primary state:

- `VERIFYING`.

### RECOVER

Reconstructs the transaction execution from a persisted commit-intent state.

Primary state:

- `COMMITTING`.

### FINALIZE

Completes a transaction whose commit operation has already been sufficiently established.

### COMPLETE

Confirms that a transaction already marked `COMMITTED` remains complete without executing a duplicate commit.

### QUARANTINE

Isolates transactions whose persisted state cannot be safely mapped to a valid recovery path.

## 7. Crash and Fault Injection Model

Fault injection is used to validate recovery behavior at defined transaction boundaries.

Current fault points:

```text
NONE
AFTER_PREPARED
DURING_WRITE
AFTER_WRITE
DURING_VERIFY
AFTER_VERIFY
DURING_COMMIT
AFTER_COMMIT
```

The injected fault raises a controlled runtime failure at the selected transaction boundary.

The purpose is to simulate interruption while preserving the persisted journal state produced before the fault.

Expected recovery coverage:

```text
AFTER_PREPARED → PREPARED → ROLLBACK
DURING_WRITE  → WRITING  → ROLLBACK
AFTER_WRITE   → WRITING  → ROLLBACK
DURING_VERIFY → VERIFYING → REVERIFY
AFTER_VERIFY  → VERIFYING → REVERIFY
DURING_COMMIT → COMMITTING → RECOVER
AFTER_COMMIT  → COMMITTING → RECOVER / FINALIZE
NONE          → COMMITTED
```

The fault-injection suite validates the logical recovery model using controlled process failures.

True operating-system process termination and physical power-loss behavior are separate validation layers and are not implied by simulated runtime exceptions.


---

## 8. Recovery Idempotency

Recovery operations must be safe to execute more than once.

The same persisted transaction must produce a stable recovery result when recovery is repeated.

Required properties:

- transaction identity remains stable;
- idempotency key remains stable;
- payload hash remains stable;
- result hash remains stable after successful commit;
- an already committed transaction is not committed again;
- recovery does not create duplicate transactional effects.

The recovery engine therefore treats `COMMITTED` as an already completed state and does not re-execute the commit operation.

## 9. Duplicate Commit Protection

Duplicate commit protection prevents repeated recovery attempts from producing multiple commit effects for the same transaction.

Conceptual rule:

```text
if transaction.state == COMMITTED:
    do not execute commit again
    return existing result
```

The transaction identity and idempotency key provide stable references across recovery attempts.

Commit recovery must preserve the original transaction result rather than generating a new result for each restart.

## 10. Persistent Restart Recovery

Persistent restart recovery validates that transaction state survives process termination and can be reconstructed by a new process instance.

The restart sequence is:

```text
Process A
   │
   ├── execute transaction
   │
   ├── persist state
   │
   ├── process termination / crash
   │
   ▼
Persistent Journal
   │
   ▼
Process B
   │
   ├── load journal
   ├── reconstruct transaction
   ├── determine recovery action
   └── execute recovery
```

The restart model must preserve transaction identity and the durable transaction evidence required for recovery.

## 11. Validation Matrix

The transaction and recovery model is validated through the following layers:

| Layer | Validation | Status |
|---|---|---|
| State Model | Transaction states and lifecycle | PASS |
| Lifecycle | Normal execution flow | PASS |
| Transition Validation | Valid state transitions | PASS |
| State Machine Audit | Transition implementation audit | PASS |
| Recovery Implementation | Recovery actions | PASS |
| Fault Injection | Crash boundaries | PASS |
| Recovery Idempotency | Repeated recovery | PASS |
| Persistent Journal | Durable transaction state | PASS |
| True Process Restart | OS-level restart behavior | PASS |

## 12. Current Validation Evidence

### 15.2.6-F — Recovery Implementation

Validated recovery scenarios:

- PREPARED rollback;
- WRITING rollback;
- VERIFY recovery;
- COMMIT finalization;
- already committed recovery;
- failed verification;
- unknown-state quarantine.

Result: `7/7 PASS`.

### 15.2.6-G — Crash Recovery & Fault Injection

Validated fault scenarios:

- after prepared;
- during write;
- after write;
- during verify;
- after verify;
- during commit;
- after commit;
- no fault.

Result: `8/8 PASS`.

The current implementation uses controlled runtime fault injection. This does not by itself prove behavior under operating-system process kill or physical power loss.

### 15.2.6-H — Recovery Idempotency & Duplicate Commit Protection

Validated properties:

- committed recovery is idempotent;
- finalization is exactly-once according to the current test model;
- rollback recovery behavior is controlled;
- duplicate commit from recovery is prevented;
- transaction identity and result identity remain stable.

Result: `5/5 PASS`.

## 13. 15.2.6-E Status

The Transaction & Recovery Model defines the documented baseline for:

- transaction state;
- state semantics;
- persistent journal;
- recovery decisions;
- recovery actions;
- crash and fault injection;
- recovery idempotency;
- duplicate commit protection;
- persistent restart recovery;
- validation evidence.

Documentation status: `COMPLETE`.

Persistent restart recovery was subsequently validated by the dedicated 15.2.6-I validation layer.

Current operational regression confirms the transaction/recovery test suite passes with 31/31 tests.

The historical 15.2.6-F, 15.2.6-G, 15.2.6-H and 15.2.6-I validation records are preserved as separate evidence layers.

---

**Document:** `docs/architecture/TRANSACTION_RECOVERY_MODEL.md`
**Phase:** `15.2.6`
**Component:** Transaction & Recovery Model
**Status:** AUDITED BASELINE

