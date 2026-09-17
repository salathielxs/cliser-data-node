import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from node.access_control import (
    AccessDenied,
    create_principal,
    has_permission,
    require_permission,
)


NAMESPACE_A = "security_test"
NAMESPACE_B = "other_test"


def main():
    print("\nCLISER DATA NODE — ACCESS CONTROL TEST")
    print("=" * 50)

    admin = create_principal(
        identity_id="identity-admin",
        role="ADMIN",
    )

    owner = create_principal(
        identity_id="identity-owner",
        role="OWNER",
        namespace=NAMESPACE_A,
    )

    writer = create_principal(
        identity_id="identity-writer",
        role="WRITER",
        namespace=NAMESPACE_A,
    )

    reader = create_principal(
        identity_id="identity-reader",
        role="READER",
        namespace=NAMESPACE_A,
    )

    print("PRINCIPALS CREATED: OK")

    assert has_permission(
        admin,
        "node.manage",
    )

    assert has_permission(
        owner,
        "object.create",
        namespace=NAMESPACE_A,
    )

    assert has_permission(
        writer,
        "object.create",
        namespace=NAMESPACE_A,
    )

    assert has_permission(
        reader,
        "object.read",
        namespace=NAMESPACE_A,
    )

    print("ROLE PERMISSIONS: OK")

    assert not has_permission(
        reader,
        "object.create",
        namespace=NAMESPACE_A,
    )

    print("READER WRITE DENIED: OK")

    assert not has_permission(
        writer,
        "namespace.manage",
        namespace=NAMESPACE_A,
    )

    print("WRITER ADMIN DENIED: OK")

    assert not has_permission(
        owner,
        "object.read",
        namespace=NAMESPACE_B,
    )

    print("NAMESPACE ISOLATION: OK")

    require_permission(
        owner,
        "object.create",
        namespace=NAMESPACE_A,
    )

    print("AUTHORIZED OPERATION: OK")

    denied = False

    try:
        require_permission(
            reader,
            "object.delete",
            namespace=NAMESPACE_A,
        )
    except AccessDenied:
        denied = True

    assert denied

    print("UNAUTHORIZED OPERATION REJECTED: OK")

    denied_namespace = False

    try:
        require_permission(
            owner,
            "object.read",
            namespace=NAMESPACE_B,
        )
    except AccessDenied:
        denied_namespace = True

    assert denied_namespace

    print("CROSS-NAMESPACE ACCESS REJECTED: OK")

    print("\n" + "=" * 50)
    print("ACCESS CONTROL: PASS")
    print("FASE 13.4 — CONTROLE DE ACESSO VALIDADO")
    print("=" * 50)


if __name__ == "__main__":
    main()
