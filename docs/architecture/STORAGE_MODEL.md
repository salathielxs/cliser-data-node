# CLISER DATA NODE
## Storage Model — 15.2.4

**Status:** AUDITED BASELINE
**Registry:** `data/registry.db`
**Physical root:** `storage/`

---

## 1. Purpose

This document describes the relationship between logical data structures in the Registry and their physical representation in the CLISER DATA NODE storage layer.

The document is generated from the active Registry and current filesystem.

## 2. Storage Hierarchy

```text
                    CLISER DATA NODE
                           │
                           ▼
                       NAMESPACE
                           │
                           ▼
                         OBJECT
                       /        \
                      /          \
             DIRECT STORAGE     MANIFEST
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

## 3. Physical Storage Root

- Root: `storage`
- Objects directory: `storage/objects`
- Blocks directory: `storage/blocks`

The physical storage layer is separated from the SQLite Registry.

The Registry stores metadata and relationships; the filesystem stores physical content.

## 4. Object Storage

Objects represent logical resources.

An object can use direct physical storage through `storage_path` or use a manifest-based representation.

The object Registry contains:

- object_id
- content_hash
- size
- storage_path
- namespace
- created_at
- status

## 5. Block Storage

Blocks represent physical content units used by manifest-based objects.

Block metadata includes:

- block_id
- content_hash
- size
- storage_path
- created_at
- status
- ref_count

## 6. Manifest Storage

A manifest provides the logical mapping between an object and its ordered blocks.

```text
OBJECT
  │
  ▼
MANIFEST
  │
  ▼
MANIFEST_BLOCKS
  │
  ├── block_index = 0 → BLOCK
  ├── block_index = 1 → BLOCK
  ├── block_index = 2 → BLOCK
  └── ...
```

## 7. Registry ↔ Filesystem

The storage model requires correspondence between Registry records and physical files.

```text
Registry Object
      │
      └── storage_path ─────► Physical Object

Registry Block
      │
      └── storage_path ─────► Physical Block
```

## 8. Storage Integrity

The integrity relationship is:

```text
REGISTRY
   │
   ├── OBJECTS ───────────► storage/objects/
   │
   ├── BLOCKS ────────────► storage/blocks/
   │
   └── MANIFESTS ─────────► BLOCK REFERENCES
```

Integrity validation must detect:

1. Registry object without required physical file.
2. Physical object without Registry record.
3. Registry block without physical file.
4. Physical block without Registry record.
5. Manifest referencing an invalid block.
6. Incorrect block reference counts.
7. Invalid storage paths.

## 9. Garbage Collection Relationship

Physical block deletion is separated from logical object deletion.

```text
OBJECT DELETE
     │
     ▼
MANIFEST DELETE
     │
     ▼
MANIFEST_BLOCKS REMOVED
     │
     ▼
ref_count RECALCULATED
     │
     ▼
ref_count = 0
     │
     ▼
PENDING GC
     │
     ▼
PHYSICAL BLOCK REMOVAL
```

## 10. Current Storage Snapshot

- Registry objects: **346**
- Active objects: **287**
- Deleted objects: **59**
- Registry blocks: **41**
- Active blocks: **41**
- Manifests: **196**
- Manifest block records: **208**

- Physical object files: **150**
- Physical object bytes: **1613**
- Physical block files: **41**
- Physical block bytes: **9869985**
- Active zero-reference blocks pending GC: **1**

## 11. Storage Consistency

The authoritative consistency checks are performed by the final structural audit.

The audit compares Registry state with physical storage and validates block reference relationships.

## 12. Storage Lifecycle

```text
CREATE
  │
  ▼
ALLOCATE
  │
  ▼
WRITE
  │
  ▼
VERIFY
  │
  ▼
COMMIT
  │
  ▼
ACTIVE
  │
  ▼
DELETE
  │
  ▼
PENDING GC
  │
  ▼
RECLAIM
```

## 13. Design Principles

- Registry metadata is authoritative for logical state.
- Physical storage contains content referenced by Registry metadata.
- Logical deletion and physical reclamation are separate operations.
- Block reference counts are derived from manifest relationships.
- Garbage Collection operates only on blocks eligible for reclamation.
- Storage integrity must be auditable.

## 14. Current Status

This document represents the storage architecture observed during Phase 15.2.4.

Generated from the active Registry and filesystem.
