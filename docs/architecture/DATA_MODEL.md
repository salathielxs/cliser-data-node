# CLISER DATA NODE
## Data Model — 15.2.3

**Status:** AUDITED BASELINE
**Database:** `data/registry.db`
**Engine:** SQLite

---

## 1. Purpose

This document describes the persistent relational data model of the CLISER DATA NODE Registry.

The schema is extracted directly from the active SQLite database.

## 2. Tables

- `api_credentials`
- `blocks`
- `manifest_blocks`
- `manifests`
- `namespaces`
- `objects`
- `quotas`
- `transaction_journal`
- `transactions`

## 3. Table Definitions

### 3.1 `api_credentials`

| # | Column | Type | NOT NULL | Default | PK |
|---:|---|---|---:|---|---:|
| 0 | `credential_id` | `TEXT` | 0 | `` | 1 |
| 1 | `token_hash` | `TEXT` | 1 | `` | 0 |
| 2 | `identity_id` | `TEXT` | 1 | `` | 0 |
| 3 | `role` | `TEXT` | 1 | `` | 0 |
| 4 | `namespace` | `TEXT` | 0 | `` | 0 |
| 5 | `status` | `TEXT` | 1 | `'ACTIVE'` | 0 |
| 6 | `created_at` | `TEXT` | 1 | `` | 0 |
| 7 | `updated_at` | `TEXT` | 1 | `` | 0 |

**Indexes**

- `idx_api_credentials_status` — NON-UNIQUE
- `idx_api_credentials_namespace` — NON-UNIQUE
- `idx_api_credentials_identity` — NON-UNIQUE
- `idx_api_credentials_token_hash` — NON-UNIQUE
- `sqlite_autoindex_api_credentials_2` — UNIQUE
- `sqlite_autoindex_api_credentials_1` — UNIQUE

### 3.2 `blocks`

| # | Column | Type | NOT NULL | Default | PK |
|---:|---|---|---:|---|---:|
| 0 | `block_id` | `TEXT` | 0 | `` | 1 |
| 1 | `content_hash` | `TEXT` | 1 | `` | 0 |
| 2 | `size` | `INTEGER` | 1 | `` | 0 |
| 3 | `storage_path` | `TEXT` | 1 | `` | 0 |
| 4 | `created_at` | `TEXT` | 1 | `` | 0 |
| 5 | `status` | `TEXT` | 1 | `'ACTIVE'` | 0 |
| 6 | `ref_count` | `INTEGER` | 1 | `0` | 0 |

**Indexes**

- `idx_blocks_status` — NON-UNIQUE
- `sqlite_autoindex_blocks_1` — UNIQUE

### 3.3 `manifest_blocks`

| # | Column | Type | NOT NULL | Default | PK |
|---:|---|---|---:|---|---:|
| 0 | `object_id` | `TEXT` | 1 | `` | 1 |
| 1 | `block_index` | `INTEGER` | 1 | `` | 2 |
| 2 | `block_id` | `TEXT` | 1 | `` | 0 |
| 3 | `size` | `INTEGER` | 1 | `` | 0 |

**Foreign Keys**

| Column | References | ON UPDATE | ON DELETE |
|---|---|---|---|
| `block_id` | `blocks.block_id` | `NO ACTION` | `NO ACTION` |
| `object_id` | `manifests.object_id` | `NO ACTION` | `CASCADE` |

**Indexes**

- `idx_manifest_blocks_block` — NON-UNIQUE
- `sqlite_autoindex_manifest_blocks_1` — UNIQUE

### 3.4 `manifests`

| # | Column | Type | NOT NULL | Default | PK |
|---:|---|---|---:|---|---:|
| 0 | `object_id` | `TEXT` | 0 | `` | 1 |
| 1 | `namespace` | `TEXT` | 1 | `'default'` | 0 |
| 2 | `total_size` | `INTEGER` | 1 | `` | 0 |
| 3 | `block_size` | `INTEGER` | 1 | `` | 0 |
| 4 | `block_count` | `INTEGER` | 1 | `` | 0 |
| 5 | `created_at` | `TEXT` | 1 | `` | 0 |
| 6 | `status` | `TEXT` | 1 | `'ACTIVE'` | 0 |

**Foreign Keys**

| Column | References | ON UPDATE | ON DELETE |
|---|---|---|---|
| `object_id` | `objects.object_id` | `NO ACTION` | `NO ACTION` |

**Indexes**

- `idx_manifests_status` — NON-UNIQUE
- `idx_manifests_namespace` — NON-UNIQUE
- `sqlite_autoindex_manifests_1` — UNIQUE

### 3.5 `namespaces`

| # | Column | Type | NOT NULL | Default | PK |
|---:|---|---|---:|---|---:|
| 0 | `namespace` | `TEXT` | 0 | `` | 1 |
| 1 | `status` | `TEXT` | 1 | `'ACTIVE'` | 0 |
| 2 | `quota_bytes` | `INTEGER` | 1 | `0` | 0 |
| 3 | `created_at` | `TEXT` | 1 | `` | 0 |
| 4 | `updated_at` | `TEXT` | 1 | `` | 0 |

**Indexes**

- `sqlite_autoindex_namespaces_1` — UNIQUE

### 3.6 `objects`

| # | Column | Type | NOT NULL | Default | PK |
|---:|---|---|---:|---|---:|
| 0 | `object_id` | `TEXT` | 0 | `` | 1 |
| 1 | `content_hash` | `TEXT` | 1 | `` | 0 |
| 2 | `size` | `INTEGER` | 1 | `` | 0 |
| 3 | `storage_path` | `TEXT` | 0 | `` | 0 |
| 4 | `namespace` | `TEXT` | 1 | `'default'` | 0 |
| 5 | `created_at` | `TEXT` | 1 | `` | 0 |
| 6 | `status` | `TEXT` | 1 | `'ACTIVE'` | 0 |

**Indexes**

- `idx_objects_status` — NON-UNIQUE
- `idx_objects_namespace` — NON-UNIQUE
- `sqlite_autoindex_objects_1` — UNIQUE

### 3.7 `quotas`

| # | Column | Type | NOT NULL | Default | PK |
|---:|---|---|---:|---|---:|
| 0 | `namespace` | `TEXT` | 0 | `` | 1 |
| 1 | `quota_bytes` | `INTEGER` | 1 | `` | 0 |
| 2 | `status` | `TEXT` | 1 | `'ACTIVE'` | 0 |
| 3 | `created_at` | `TEXT` | 1 | `` | 0 |

**Indexes**

- `sqlite_autoindex_quotas_1` — UNIQUE

### 3.8 `transaction_journal`

| # | Column | Type | NOT NULL | Default | PK |
|---:|---|---|---:|---|---:|
| 0 | `transaction_id` | `TEXT` | 0 | `` | 1 |
| 1 | `phase` | `TEXT` | 1 | `` | 0 |
| 2 | `commit_marker` | `INTEGER` | 1 | `0` | 0 |
| 3 | `resources` | `TEXT` | 0 | `` | 0 |
| 4 | `verified` | `INTEGER` | 1 | `0` | 0 |
| 5 | `created_at` | `TEXT` | 1 | `` | 0 |
| 6 | `updated_at` | `TEXT` | 1 | `` | 0 |

**Foreign Keys**

| Column | References | ON UPDATE | ON DELETE |
|---|---|---|---|
| `transaction_id` | `transactions.transaction_id` | `NO ACTION` | `CASCADE` |

**Indexes**

- `idx_transaction_journal_commit` — NON-UNIQUE
- `idx_transaction_journal_phase` — NON-UNIQUE
- `sqlite_autoindex_transaction_journal_1` — UNIQUE

### 3.9 `transactions`

| # | Column | Type | NOT NULL | Default | PK |
|---:|---|---|---:|---|---:|
| 0 | `transaction_id` | `TEXT` | 0 | `` | 1 |
| 1 | `object_id` | `TEXT` | 0 | `` | 0 |
| 2 | `namespace` | `TEXT` | 0 | `` | 0 |
| 3 | `operation` | `TEXT` | 1 | `` | 0 |
| 4 | `state` | `TEXT` | 1 | `` | 0 |
| 5 | `created_at` | `TEXT` | 1 | `` | 0 |
| 6 | `updated_at` | `TEXT` | 1 | `` | 0 |
| 7 | `error` | `TEXT` | 0 | `` | 0 |
| 8 | `metadata` | `TEXT` | 0 | `` | 0 |
| 9 | `idempotency_key` | `TEXT` | 0 | `` | 0 |
| 10 | `request_fingerprint` | `TEXT` | 0 | `` | 0 |

**Indexes**

- `idx_transactions_idempotency_unique` — UNIQUE
- `idx_transactions_namespace` — NON-UNIQUE
- `idx_transactions_object` — NON-UNIQUE
- `idx_transactions_state` — NON-UNIQUE
- `sqlite_autoindex_transactions_1` — UNIQUE

## 4. Core Relationships

The Registry represents relationships between logical objects, manifests, blocks, namespaces, quotas and transactions.

Expected logical relationships include:

- Object → Manifest
- Manifest → Manifest Blocks
- Manifest Block → Block
- Quota → Namespace
- Transaction → Transaction Journal

The authoritative relationship definitions are the foreign-key declarations extracted above.

## 5. Integrity Rules

The data model must preserve:

1. Primary-key uniqueness.
2. Foreign-key consistency.
3. Object/manifest consistency.
4. Manifest/block consistency.
5. Block reference-count consistency.
6. Namespace isolation.
7. Quota/namespace consistency.
8. Transaction/journal consistency.
9. Idempotency uniqueness.

## 6. SQLite Integrity

The active registry is validated using SQLite integrity checks and the CLISER DATA NODE structural audit.

## 7. Generation Metadata

This document was generated from the active `data/registry.db` during Phase 15.2.3.
