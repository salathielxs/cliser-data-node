import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from node.access_control import (
    AccessDenied,
    create_principal,
)
from node import namespace_manager
from node.namespace_security import (
    NamespaceSecurityError,
    require_namespace_access,
)


NAMESPACE_A = "security_ns_a"
NAMESPACE_B = "security_ns_b"


def ensure_namespace(namespace):
    if not namespace_manager.namespace_exists(namespace):
        namespace_manager.create_namespace(
            namespace,
            quota_bytes=0,
        )


def main():
    print("\nCLISER DATA NODE — NAMESPACE SECURITY TEST")
    print("=" * 50)

    ensure_namespace(NAMESPACE_A)
    ensure_namespace(NAMESPACE_B)

    owner_a = create_principal(
        identity_id="identity-owner-a",
        role="OWNER",
        namespace=NAMESPACE_A,
    )

    writer_a = create_principal(
        identity_id="identity-writer-a",
        role="WRITER",
        namespace=NAMESPACE_A,
    )

    reader_a = create_principal(
        identity_id="identity-reader-a",
        role="READER",
        namespace=NAMESPACE_A,
    )

    admin = create_principal(
        identity_id="identity-admin",
        role="ADMIN",
    )

    print("NAMESPACES READY: OK")
    print("PRINCIPALS READY: OK")

    require_namespace_access(
        owner_a,
        NAMESPACE_A,
        "object.create",
    )

    print("OWNER SAME NAMESPACE: OK")

    require_namespace_access(
        writer_a,
        NAMESPACE_A,
        "object.create",
    )

    print("WRITER SAME NAMESPACE: OK")

    require_namespace_access(
        reader_a,
        NAMESPACE_A,
        "object.read",
    )

    print("READER SAME NAMESPACE: OK")

    denied = False

    try:
        require_namespace_access(
            owner_a,
            NAMESPACE_B,
            "object.read",
        )
    except AccessDenied:
        denied = True

    assert denied

    print("OWNER CROSS-NAMESPACE DENIED: OK")

    denied = False

    try:
        require_namespace_access(
            writer_a,
            NAMESPACE_B,
            "object.create",
        )
    except AccessDenied:
        denied = True

    assert denied

    print("WRITER CROSS-NAMESPACE DENIED: OK")

    denied = False

    try:
        require_namespace_access(
            reader_a,
            NAMESPACE_B,
            "object.read",
        )
    except AccessDenied:
        denied = True

    assert denied

    print("READER CROSS-NAMESPACE DENIED: OK")

    require_namespace_access(
        admin,
        NAMESPACE_B,
        "object.create",
    )

    print("ADMIN GLOBAL ACCESS: OK")

    disabled_ns = "security_ns_disabled"

    if not namespace_manager.namespace_exists(disabled_ns):
        namespace_manager.create_namespace(
            disabled_ns,
            quota_bytes=0,
        )

    namespace_manager.disable_namespace(
        disabled_ns,
    )

    denied = False

    try:
        require_namespace_access(
            admin,
            disabled_ns,
            "object.read",
        )
    except NamespaceSecurityError:
        denied = True

    assert denied

    print("DISABLED NAMESPACE BLOCKED: OK")

    nonexistent = False

    try:
        require_namespace_access(
            admin,
            "namespace_does_not_exist",
            "object.read",
        )
    except NamespaceSecurityError:
        nonexistent = True

    assert nonexistent

    print("NONEXISTENT NAMESPACE BLOCKED: OK")

    print("\n" + "=" * 50)
    print("NAMESPACE SECURITY: PASS")
    print("FASE 13.5 — SEGURANÇA DE NAMESPACE VALIDADA")
    print("=" * 50)


if __name__ == "__main__":
    main()
