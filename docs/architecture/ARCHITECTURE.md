# CLISER DATA NODE
## Technical Architecture — 15.2

**Status:** AUDITED BASELINE
 
**Phase:** 15.2 — Technical Documentation
**Runtime:** Python / FastAPI / SQLite
**Platform:** Android / Termux / aarch64

 
---

## 1. Purpose

The CLISER DATA NODE is a modular data-storage node responsible for API access, identity, authorization, namespaces, object storage, block storage, manifests, transactions, quotas, integrity verification and lifecycle management.
 

## 2. High-Level Architecture

```text
                    CLISER DATA NODE
                           |
                    +------+------+
                    |             |
                 API LAYER     NODE CORE
                    |             |
                    +------+------+ 
                           |
                    SQLite Registry
                           |
                 Objects / Blocks
                           |
                  Physical Storage
```
 

## 3. API Layer

FastAPI provides authentication, authorization, validation, errors, rate limiting, idempotency and API access to node services.

## 4. Node Core

The node core contains access control, accounting, allocation, block management, capacity, identity, lifecycle, manifest, namespace, object, quota, recovery, registry, storage and transaction modules.

## 5. Registry

SQLite is the persistent registry for objects, blocks, manifests, namespaces, quotas, credentials and transactions.

## 6. Object Model

Objects represent logical stored resources and may use direct storage or manifest/block storage.

## 7. Block Model

Blocks represent physical content units. ref_count represents active manifest references.

## 8. Manifest Model

Manifests describe block-based objects and manifest_blocks preserves block ordering.

## 9. Object Deletion

Logical deletion is separated from physical block reclamation.

## 10. Garbage Collection

ACTIVE blocks with ref_count=0 are valid pending Garbage Collection candidates.

## 11. Transactions

Transactions provide controlled execution, commit, rollback and recovery of state-changing operations.

## 12. Idempotency

Idempotency protects object operations from duplicate execution and detects conflicting requests.

## 13. Namespaces

Namespaces provide logical isolation for stored data and related resources.

## 14. Quotas

Quotas control namespace resource allocation.

## 15. Authentication and Authorization

Bearer credentials are authenticated using hashed token representations. Current roles are ADMIN, WRITER and READER.

## 16. Integrity Model

Integrity is validated across API, transactions, registry, objects, manifests, blocks, journal and physical storage.

## 17. Recovery

Recovery operates over persistent transaction and registry state.

## 18. Health

Health evaluates database, transaction, storage and integrity conditions.

## 19. Storage Integrity

Registry metadata must correspond to physical storage.

## 20. Audited Baseline

Baseline 15.1 recorded 41 blocks, 327 objects, 185 manifests, 862 namespaces and 349 transactions. Final audit result: PASS. API suite: 171 passed, 1 warning.

## 21. Current Architectural Status

The architecture is structurally valid according to the 15.1 baseline and final audit.

## 22. Change Control

Structural changes must preserve registry integrity, object/block consistency, transaction recovery, security boundaries, namespace isolation, quotas, idempotency and physical storage correspondence.
