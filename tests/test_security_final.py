from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
STORAGE = ROOT / "storage"
DB = ROOT / "data" / "registry.db"

sys.path.insert(0, str(ROOT))

from node import crypto_identity
from node.registry import connect


def check(label, condition, detail=""):
    if condition:
        print(f"{label}: OK")
    else:
        print(f"{label}: FAIL")
        if detail:
            print(f"  {detail}")
        raise SystemExit(1)


print("CLISER DATA NODE — FINAL SECURITY AUDIT")
print("=" * 55)

# --------------------------------------------------
# 1. ESTRUTURA
# --------------------------------------------------

required = [
    ROOT / "node",
    ROOT / "cli",
    CONFIG,
    STORAGE,
    STORAGE / "objects",
    STORAGE / "blocks",
    STORAGE / "temp",
    ROOT / "data",
    DB,
]

check(
    "CRITICAL STRUCTURE",
    all(path.exists() for path in required)
)

# --------------------------------------------------
# 2. IDENTIDADE PROTEGIDA
# --------------------------------------------------

identity_path = CONFIG / "crypto_identity.json"

with open(identity_path, "r", encoding="utf-8") as f:
    identity = json.load(f)

check(
    "PROTECTED IDENTITY",
    "private_key" not in identity
    and "private_key_protected" in identity
)

protected = identity["private_key_protected"]

check(
    "AES-256-GCM",
    protected.get("algorithm") == "AES-256-GCM"
)

check(
    "SCRYPT KDF",
    protected.get("kdf") == "scrypt"
)

check(
    "ED25519 IDENTITY",
    identity.get("algorithm") == "Ed25519"
)

# --------------------------------------------------
# 3. PERMISSÕES DA IDENTIDADE
# --------------------------------------------------

mode = os.stat(identity_path).st_mode & 0o777

check(
    "IDENTITY PERMISSIONS 600",
    mode == 0o600,
    f"mode atual: {oct(mode)}"
)

# --------------------------------------------------
# 4. SEGREDOS EM CONFIG
# --------------------------------------------------

secret_hits = []

for path in CONFIG.rglob("*"):
    if not path.is_file():
        continue

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="ignore"
        )
    except Exception:
        continue

    if '"private_key"' in text:
        secret_hits.append(str(path))

check(
    "PLAINTEXT PRIVATE KEY ABSENT",
    len(secret_hits) == 0,
    "\n".join(secret_hits)
)

# --------------------------------------------------
# 5. CHAVE INICIALMENTE BLOQUEADA
# --------------------------------------------------

check(
    "PRIVATE KEY INITIAL LOCK",
    crypto_identity.is_unlocked() is False
)

# --------------------------------------------------
# 6. STORAGE
# --------------------------------------------------

for directory in [
    STORAGE,
    STORAGE / "objects",
    STORAGE / "blocks",
    STORAGE / "temp",
]:
    mode = os.stat(directory).st_mode & 0o777

    check(
        f"STORAGE PERMISSIONS {directory.name}",
        not (mode & 0o002),
        f"world-write encontrado: {oct(mode)}"
    )

# --------------------------------------------------
# 7. TEMP
# --------------------------------------------------

temp_files = [
    p for p in (STORAGE / "temp").rglob("*")
    if p.is_file()
]

check(
    "TEMP STORAGE CLEAN",
    len(temp_files) == 0,
    "\n".join(map(str, temp_files))
)

# --------------------------------------------------
# 8. SQLITE
# --------------------------------------------------

conn = connect()

integrity = conn.execute(
    "PRAGMA integrity_check"
).fetchone()[0]

check(
    "SQLITE INTEGRITY",
    integrity == "ok",
    integrity
)

foreign_keys = conn.execute(
    "PRAGMA foreign_keys"
).fetchone()[0]

check(
    "SQLITE FOREIGN KEYS",
    foreign_keys == 1
)

# --------------------------------------------------
# 9. SCHEMA CRÍTICO
# --------------------------------------------------

tables = {
    row[0]
    for row in conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table'"
    ).fetchall()
}

required_tables = {
    "namespaces",
    "objects",
    "blocks",
    "manifests",
    "manifest_blocks",
    "quotas",
    "transactions",
    "transaction_journal",
}

check(
    "CRITICAL DATABASE TABLES",
    required_tables.issubset(tables)
)

# --------------------------------------------------
# 10. JOURNAL
# --------------------------------------------------

# Journal:
# commit_marker=0 não significa necessariamente "pendente".
# Transações em ROLLBACK podem terminar sem commit marker.
# O que realmente importa é:
#   1. não haver transações em estado recuperável;
#   2. COMMITTED possuir commit marker;
#   3. não haver estados desconhecidos.

pending_transactions = conn.execute(
    """
    SELECT COUNT(*)
    FROM transactions
    WHERE state IN (
        'PREPARED',
        'WRITING',
        'VERIFYING',
        'COMMITTING'
    )
    """
).fetchone()[0]

committed_without_marker = conn.execute(
    """
    SELECT COUNT(*)
    FROM transactions t
    JOIN transaction_journal j
      ON j.transaction_id = t.transaction_id
    WHERE t.state = 'COMMITTED'
      AND j.commit_marker = 0
    """
).fetchone()[0]

unknown_states = conn.execute(
    """
    SELECT COUNT(*)
    FROM transactions
    WHERE state NOT IN (
        'PREPARED',
        'WRITING',
        'VERIFYING',
        'COMMITTING',
        'COMMITTED',
        'FAILED',
        'ROLLBACK'
    )
    """
).fetchone()[0]

check(
    "JOURNAL RECOVERY STATE CLEAN",
    pending_transactions == 0,
    f"transações recuperáveis: {pending_transactions}"
)

check(
    "COMMITTED TRANSACTIONS HAVE MARKER",
    committed_without_marker == 0,
    f"committed sem marker: {committed_without_marker}"
)

check(
    "TRANSACTION STATES VALID",
    unknown_states == 0,
    f"estados desconhecidos: {unknown_states}"
)

# --------------------------------------------------
# 11. TRANSAÇÕES
# --------------------------------------------------

pending_transactions = conn.execute(
    """
    SELECT COUNT(*)
    FROM transactions
    WHERE state IN (
        'PREPARED',
        'WRITING',
        'VERIFYING',
        'COMMITTING'
    )
    """
).fetchone()[0]

check(
    "NO PENDING TRANSACTIONS",
    pending_transactions == 0,
    f"pendentes: {pending_transactions}"
)

# --------------------------------------------------
# 12. NAMESPACES
# --------------------------------------------------

invalid_namespaces = conn.execute(
    """
    SELECT namespace
    FROM namespaces
    WHERE namespace = ''
       OR namespace IS NULL
    """
).fetchall()

check(
    "NAMESPACE VALIDITY",
    len(invalid_namespaces) == 0
)

# --------------------------------------------------
# 13. OBJECT INTEGRITY
# --------------------------------------------------

objects = conn.execute(
    """
    SELECT object_id, content_hash, size, namespace
    FROM objects
    WHERE status = 'ACTIVE'
    """
).fetchall()

check(
    "ACTIVE OBJECT REGISTRY",
    all(
        object_id and content_hash and size >= 0 and namespace
        for object_id, content_hash, size, namespace in objects
    )
)

# --------------------------------------------------
# 14. BLOCK REGISTRY
# --------------------------------------------------

blocks = conn.execute(
    """
    SELECT block_id, content_hash, size, storage_path
    FROM blocks
    WHERE status = 'ACTIVE'
    """
).fetchall()

missing_blocks = []

for block_id, content_hash, size, storage_path in blocks:
    path = ROOT / storage_path

    if not path.exists():
        missing_blocks.append(block_id)
        continue

    if path.stat().st_size != size:
        missing_blocks.append(block_id)

check(
    "PHYSICAL BLOCK REGISTRY",
    len(missing_blocks) == 0,
    "\n".join(missing_blocks)
)

# --------------------------------------------------
# 15. MANIFEST INTEGRITY
# --------------------------------------------------

manifest_errors = []

manifests = conn.execute(
    """
    SELECT object_id, total_size, block_count
    FROM manifests
    WHERE status = 'ACTIVE'
    """
).fetchall()

for object_id, total_size, block_count in manifests:
    count = conn.execute(
        """
        SELECT COUNT(*)
        FROM manifest_blocks
        WHERE object_id = ?
        """,
        (object_id,)
    ).fetchone()[0]

    if count != block_count:
        manifest_errors.append(object_id)

check(
    "MANIFEST STRUCTURAL INTEGRITY",
    len(manifest_errors) == 0,
    "\n".join(manifest_errors)
)

# --------------------------------------------------
# 16. FOREIGN KEY VIOLATIONS
# --------------------------------------------------

fk_errors = conn.execute(
    "PRAGMA foreign_key_check"
).fetchall()

check(
    "FOREIGN KEY CONSISTENCY",
    len(fk_errors) == 0,
    str(fk_errors)
)

conn.close()

# --------------------------------------------------
# 17. PYTHON COMPILATION
# --------------------------------------------------

result = subprocess.run(
    [
        sys.executable,
        "-m",
        "compileall",
        "-q",
        str(ROOT / "node"),
        str(ROOT / "cli"),
        str(ROOT / "tests"),
    ],
    cwd=ROOT,
)

check(
    "PYTHON COMPILE",
    result.returncode == 0
)

# --------------------------------------------------
# FINAL
# --------------------------------------------------

print()
print("=" * 55)
print("FINAL SECURITY AUDIT: PASS")
print("FASE 13.8 — MODELO DE SEGURANÇA CONSOLIDADO")
print("=" * 55)
