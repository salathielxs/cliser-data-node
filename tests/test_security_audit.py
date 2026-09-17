from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
STORAGE = ROOT / "storage"
DB = ROOT / "data" / "registry.db"


def ok(label: str):
    print(f"{label}: OK")


def fail(label: str, detail: str = ""):
    print(f"{label}: FAIL")
    if detail:
        print(f"  {detail}")
    raise SystemExit(1)


def main():
    print("CLISER DATA NODE — SECURITY AUDIT")
    print("=" * 50)

    # --------------------------------------------------
    # 1. Estrutura crítica
    # --------------------------------------------------
    required_paths = [
        ROOT / "node",
        ROOT / "tests",
        CONFIG,
        STORAGE,
        STORAGE / "objects",
        STORAGE / "blocks",
        STORAGE / "temp",
        ROOT / "data",
        DB,
    ]

    for path in required_paths:
        if not path.exists():
            fail("CRITICAL PATHS", str(path))

    ok("CRITICAL PATHS")

    # --------------------------------------------------
    # 2. Identidade criptográfica
    # --------------------------------------------------
    identity_path = CONFIG / "crypto_identity.json"

    if not identity_path.exists():
        fail("IDENTITY FILE")

    identity = json.loads(
        identity_path.read_text(encoding="utf-8")
    )

    if "private_key" in identity:
        fail(
            "PLAINTEXT PRIVATE KEY",
            "Campo private_key encontrado."
        )

    if "private_key_protected" not in identity:
        fail("PROTECTED PRIVATE KEY")

    if identity.get("key_protection") != "AES-256-GCM":
        fail("KEY PROTECTION ALGORITHM")

    if identity.get("algorithm") != "Ed25519":
        fail("IDENTITY ALGORITHM")

    ok("PROTECTED IDENTITY")

    # --------------------------------------------------
    # 3. Permissão do arquivo de identidade
    # --------------------------------------------------
    mode = identity_path.stat().st_mode & 0o777

    if mode != 0o600:
        fail(
            "IDENTITY FILE PERMISSIONS",
            f"esperado 600, encontrado {oct(mode)}"
        )

    ok("IDENTITY FILE PERMISSIONS")

    # --------------------------------------------------
    # 4. Backup legado
    # --------------------------------------------------
    backup = CONFIG / "crypto_identity.json.backup"

    if backup.exists():
        backup_mode = backup.stat().st_mode & 0o777

        print(
            "LEGACY PLAINTEXT BACKUP: PRESENT"
        )
        print(
            f"  permissions: {oct(backup_mode)}"
        )

        backup_data = json.loads(
            backup.read_text(encoding="utf-8")
        )

        if "private_key" in backup_data:
            print(
                "  WARNING: backup contém chave privada "
                "em texto aberto."
            )
    else:
        ok("LEGACY PLAINTEXT BACKUP ABSENT")

    # --------------------------------------------------
    # 5. Diretórios de armazenamento
    # --------------------------------------------------
    for directory in [
        STORAGE,
        STORAGE / "objects",
        STORAGE / "blocks",
        STORAGE / "temp",
    ]:
        mode = directory.stat().st_mode & 0o777

        if mode & 0o002:
            fail(
                "STORAGE PERMISSIONS",
                f"{directory} possui escrita pública."
            )

    ok("STORAGE PERMISSIONS")

    # --------------------------------------------------
    # 6. SQLite integrity_check
    # --------------------------------------------------
    from node.registry import connect

    conn = connect()

    result = conn.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]

    if result != "ok":
        conn.close()
        fail(
            "SQLITE INTEGRITY",
            str(result)
        )

    foreign_keys = conn.execute(
        "PRAGMA foreign_keys"
    ).fetchone()[0]

    conn.close()

    if foreign_keys != 1:
        fail(
            "SQLITE FOREIGN KEYS",
            "Conexão do registry não ativou foreign_keys."
        )

    ok("SQLITE INTEGRITY")
    ok("SQLITE FOREIGN KEYS")

    # --------------------------------------------------
    # 7. Arquivos temporários
    # --------------------------------------------------
    temp_files = [
        p for p in (STORAGE / "temp").rglob("*")
        if p.is_file()
    ]

    if temp_files:
        print(
            f"TEMP FILES: WARNING ({len(temp_files)})"
        )
        for path in temp_files[:10]:
            print(f"  {path}")
    else:
        ok("TEMP STORAGE CLEAN")

    # --------------------------------------------------
    # 8. Compilação Python
    # --------------------------------------------------
    import compileall

    compiled = compileall.compile_dir(
        ROOT / "node",
        quiet=1,
    )

    if not compiled:
        fail("PYTHON COMPILE")

    ok("PYTHON COMPILE")

    # --------------------------------------------------
    # 9. Proteção contra arquivos secretos óbvios
    # --------------------------------------------------
    suspicious = []

    for path in CONFIG.rglob("*"):
        if not path.is_file():
            continue

        if path.name.endswith(".py"):
            continue

        try:
            content = path.read_text(
                encoding="utf-8"
            )
        except Exception:
            continue

        if '"private_key":' in content:
            suspicious.append(path)

    if suspicious:
        fail(
            "SECRET SCAN",
            "Arquivos contendo private_key: "
            + ", ".join(map(str, suspicious))
        )

    ok("SECRET SCAN")

    # --------------------------------------------------
    # FINAL
    # --------------------------------------------------
    print()
    print("=" * 50)
    print("SECURITY AUDIT: PASS")
    print("FASE 13.7.1 — AUDITORIA ESTRUTURAL VALIDADA")
    print("=" * 50)


if __name__ == "__main__":
    main()
