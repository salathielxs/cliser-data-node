# CLISER DATA NODE
## Storage Integrity Model — 15.2.5

**Status:** AUDITED BASELINE
**Mode:** READ-ONLY
**Registry:** `data/registry.db`
**Physical root:** `storage/`

---

## 1. Purpose

This document defines the integrity relationship between the logical Registry and physical storage.

No mutation, deletion, migration or garbage collection is performed by this audit.

## 2. Integrity Chain

```text
NAMESPACE
    │
    ▼
OBJECT
    │
    ├──────────────► DIRECT STORAGE
    │
    └──────────────► MANIFEST
                         │
                         ▼
                   MANIFEST_BLOCKS
                         │
                         ▼
                       BLOCK
                         │
                         ▼
                 PHYSICAL STORAGE
```

## 3. Integrity Rules

### 3.1 Object → Physical Storage

An object with a direct `storage_path` must resolve to an existing physical file.

### 3.2 Block → Physical Storage

Every registered block must resolve to an existing physical block file.

### 3.3 Manifest → Object

Every manifest must correspond to a registered object.

### 3.4 Manifest Block → Block

Every `manifest_blocks.block_id` must reference a registered block.

### 3.5 Reference Count

`blocks.ref_count` must equal the number of references in `manifest_blocks`.

### 3.6 Manifest Block Count

`manifests.block_count` must equal the number of associated `manifest_blocks` records.

### 3.7 Physical Orphans

Physical files must not exist outside the Registry's known storage paths unless explicitly classified as temporary or operational data.

### 3.8 Physical Size

For registered physical files, filesystem size must match Registry metadata.

## 4. Garbage Collection Semantics

An `ACTIVE` block with `ref_count=0` is classified as a pending Garbage Collection candidate.

```text
ACTIVE BLOCK
     │
     ├── ref_count > 0 → REFERENCED
     │
     └── ref_count = 0 → PENDING GC
```

A pending-GC block is not automatically considered an integrity failure.

## 5. Current Audit

- Registry objects: **346**
- Registry blocks: **41**
- Manifests: **196**
- Manifest blocks: **208**
- Physical object files: **150**
- Physical block files: **41**
- Pending-GC blocks: **1**

## 6. Official Integrity Results

The official storage auditor `scripts/audit_14256_storage.py`
was executed during Phase 15.2.5-C3.

### 6.1 Block Registry

- **PASS** Registry blocks = 41
- **PASS** Physical block files = 41
- **PASS** Physical blocks without Registry = 0
- **PASS** Registry blocks without physical file = 0
- **PASS** Active block size validation errors = 0
- **PASS** Active block SHA-256 validation errors = 0
- **PASS** Block storage path validation errors = 0

### 6.2 Object Storage

- **PASS** Registry objects = 346
- **PASS** Physical object files = 150
- **PASS** Active objects missing physical file = 0
- **PASS** Active object size validation errors = 0
- **PASS** Active object SHA-256 validation errors = 0
- **PASS** Physical objects without Registry = 0

### 6.3 Object Classification

- Active objects = 287
- Deleted objects = 59
- Active logical-only objects = 157
- Physical object files = 150

Logical-only ACTIVE objects are valid when their data is represented
through the manifest/block storage model.

### 6.4 Manifest Integrity

- Active manifests = 157
- **PASS** Active manifest integrity errors = 0
- **PASS** Manifest → Object relationships = 0 errors
- **PASS** Manifest → Block relationships = 0 errors

Historical DELETED manifests without remaining `manifest_blocks`
records are valid terminal states.

The previously observed 39 manifest count differences were classified
as historical DELETED/test residues. No ACTIVE manifest presented a
count inconsistency.

### 6.5 Block Reference Integrity

- Pending-GC blocks = 1
- **PASS** Block reference consistency errors = 0

An ACTIVE block with `ref_count=0` is classified as `PENDING_GC`.
This state is transitional and is not itself an integrity failure.

### 6.6 Database Integrity

- **PASS** SQLite `integrity_check` = `ok`
- **PASS** Foreign-key violations = 0

### 6.7 Physical ↔ Registry Reconciliation

- **PASS** Physical blocks without Registry = 0
- **PASS** Registry blocks without physical file = 0
- **PASS** Physical objects without Registry = 0
- **PASS** Required active object files missing = 0

The official auditor validates physical files by their Registry object/block
identifiers. No physical-storage orphan was detected.

## 7. Audit Interpretation

The official 15.2.5-C3 audit establishes that the logical Registry,
physical storage, manifests and block references are mutually consistent.

The earlier diagnostic that reported 150 physical object orphans and
41 physical block orphans was a temporary diagnostic with an incompatible
path representation. Those values do not represent actual storage orphans
and are superseded by the official auditor results.

The earlier 39 manifest count findings were independently investigated
during 15.2.5-A and 15.2.5-B. All were DELETED historical/test manifests
with zero remaining `manifest_blocks`. No ACTIVE manifest was affected.

Therefore:

- no storage corruption was identified;
- no physical orphan was identified;
- no active manifest inconsistency was identified;
- no block reference inconsistency was identified;
- no corrective storage mutation is required by 15.2.5-D.

## 8. Corrective Action Policy

No automatic corrective action is performed by the integrity model.

Eligible operations remain separate from integrity validation:

1. rebuild block reference counts;
2. classify blocks as `PENDING_GC`;
3. execute Garbage Collection;
4. remove physical block data only after eligibility is confirmed;
5. remove corresponding Registry records;
6. audit the resulting state.

Any corrective operation must be separately executed and audited.

## 9. Official Status

**15.2.5-D — PASS**

Storage integrity model reconciled against the official 15.2.5-C3
storage auditor.

No critical inconsistency identified.

## 7. Interpretation

A zero count means that the corresponding integrity condition was satisfied during this read-only audit.

Non-zero findings require classification before any corrective mutation.

## 8. Required Corrective Actions

No automatic corrective action is performed by this document generator.

Potential actions include:

- reconcile Registry metadata;
- restore missing physical content;
- remove explicitly classified physical orphans;
- rebuild reference counts;
- run Garbage Collection for eligible blocks;
- repair manifest relationships.

Any corrective operation must be separately audited.

## 9. Status

The integrity model is generated directly from the active Registry and current filesystem.

