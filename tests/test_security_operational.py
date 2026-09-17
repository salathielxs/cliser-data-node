from __future__ import annotations

from getpass import getpass

from node import crypto_identity
from node import object_signature
from node.access_control import (
    AccessDenied,
    create_principal,
    require_permission,
)
from node.namespace_security import (
    NamespaceSecurityError,
    require_namespace_read,
)


def ok(label: str):
    print(f"{label}: OK")


def fail(label: str, detail: str = ""):
    print(f"{label}: FAIL")
    if detail:
        print(f"  {detail}")
    raise SystemExit(1)


def main():
    print("CLISER DATA NODE — OPERATIONAL SECURITY TEST")
    print("=" * 50)

    password = getpass("Senha da identidade: ")

    # --------------------------------------------------
    # 1. Identidade protegida
    # --------------------------------------------------
    try:
        identity = crypto_identity.load_identity()
    except Exception as exc:
        fail("IDENTITY LOAD", str(exc))

    if "private_key" in identity:
        fail(
            "PLAINTEXT PRIVATE KEY",
            "private_key encontrado."
        )

    if "private_key_protected" not in identity:
        fail(
            "PROTECTED PRIVATE KEY",
            "Chave protegida ausente."
        )

    ok("PROTECTED IDENTITY LOAD")

    # --------------------------------------------------
    # 2. Senha incorreta
    # --------------------------------------------------
    try:
        crypto_identity.unlock(
            password + "__INVALID__"
        )
    except Exception:
        ok("WRONG PASSWORD REJECTED")
    else:
        crypto_identity.lock()
        fail(
            "WRONG PASSWORD REJECTED",
            "Senha incorreta foi aceita."
        )

    # --------------------------------------------------
    # 3. Desbloqueio correto
    # --------------------------------------------------
    try:
        crypto_identity.unlock(password)
    except Exception as exc:
        fail("PRIVATE KEY UNLOCK", str(exc))

    if not crypto_identity.is_unlocked():
        fail(
            "PRIVATE KEY STATE",
            "Chave deveria estar desbloqueada."
        )

    ok("PRIVATE KEY UNLOCKED")

    # --------------------------------------------------
    # 4. Assinatura
    # --------------------------------------------------
    payload = b"CLISER-DATA-NODE-SECURITY-TEST"

    try:
        signature = crypto_identity.sign(payload)
    except Exception as exc:
        fail("SIGNATURE", str(exc))

    if not crypto_identity.verify(
        payload,
        signature,
    ):
        fail(
            "SIGNATURE VERIFICATION",
            "Assinatura não foi validada."
        )

    ok("SIGNATURE VERIFIED")

    # --------------------------------------------------
    # 5. Alteração do payload
    # --------------------------------------------------
    if crypto_identity.verify(
        b"ALTERED-PAYLOAD",
        signature,
    ):
        fail(
            "TAMPERED SIGNATURE",
            "Payload alterado foi aceito."
        )

    ok("TAMPERED SIGNATURE REJECTED")

    # --------------------------------------------------
    # 6. Lock
    # --------------------------------------------------
    crypto_identity.lock()

    if crypto_identity.is_unlocked():
        fail(
            "PRIVATE KEY LOCK",
            "Chave continua desbloqueada."
        )

    ok("PRIVATE KEY LOCKED")

    # --------------------------------------------------
    # 7. Assinatura bloqueada
    # --------------------------------------------------
    try:
        crypto_identity.sign(payload)
    except Exception:
        ok("BLOCKED SIGNING REJECTED")
    else:
        fail(
            "BLOCKED SIGNING",
            "Assinatura ocorreu sem desbloqueio."
        )

    # --------------------------------------------------
    # 8. Verificação pública continua disponível
    # --------------------------------------------------
    if not crypto_identity.verify(
        payload,
        signature,
    ):
        fail(
            "PUBLIC VERIFICATION",
            "Verificação falhou após lock."
        )

    ok("PUBLIC VERIFICATION AFTER LOCK")

    # --------------------------------------------------
    # 9. Access Control
    # --------------------------------------------------
    reader = create_principal(
        identity_id="security-reader",
        role="READER",
        namespace="security-test",
    )

    writer = create_principal(
        identity_id="security-writer",
        role="WRITER",
        namespace="security-test",
    )

    admin = create_principal(
        identity_id="security-admin",
        role="ADMIN",
    )

    try:
        require_permission(
            reader,
            "object.read",
            namespace="security-test",
        )
    except Exception as exc:
        fail(
            "READER READ",
            str(exc),
        )

    ok("READER AUTHORIZED")

    try:
        require_permission(
            reader,
            "object.create",
            namespace="security-test",
        )
    except AccessDenied:
        ok("READER WRITE DENIED")
    else:
        fail(
            "READER WRITE",
            "Reader recebeu permissão de escrita."
        )

    try:
        require_permission(
            writer,
            "object.create",
            namespace="security-test",
        )
    except Exception as exc:
        fail(
            "WRITER CREATE",
            str(exc),
        )

    ok("WRITER AUTHORIZED")

    try:
        require_permission(
            writer,
            "quota.manage",
            namespace="security-test",
        )
    except AccessDenied:
        ok("WRITER ADMIN DENIED")
    else:
        fail(
            "WRITER ADMIN",
            "Writer recebeu permissão administrativa."
        )

    try:
        require_permission(
            admin,
            "quota.manage",
            namespace="security-test",
        )
    except Exception as exc:
        fail(
            "ADMIN AUTHORIZATION",
            str(exc),
        )

    ok("ADMIN AUTHORIZED")

    # --------------------------------------------------
    # 10. Namespace isolation
    # --------------------------------------------------
    other_reader = create_principal(
        identity_id="other-reader",
        role="READER",
        namespace="other-namespace",
    )

    try:
        require_permission(
            other_reader,
            "object.read",
            namespace="security-test",
        )
    except AccessDenied:
        ok("CROSS-NAMESPACE DENIED")
    else:
        fail(
            "CROSS-NAMESPACE",
            "Acesso fora do namespace foi permitido."
        )

    # --------------------------------------------------
    # 11. Namespace security
    # --------------------------------------------------
    try:
        require_namespace_read(
            reader,
            "namespace-that-does-not-exist",
        )
    except NamespaceSecurityError:
        ok("NONEXISTENT NAMESPACE DENIED")
    else:
        fail(
            "NONEXISTENT NAMESPACE",
            "Namespace inexistente foi aceito."
        )

    # --------------------------------------------------
    # Final
    # --------------------------------------------------
    print()
    print("=" * 50)
    print("OPERATIONAL SECURITY: PASS")
    print("FASE 13.7.2 — AUDITORIA OPERACIONAL VALIDADA")
    print("=" * 50)


if __name__ == "__main__":
    main()
