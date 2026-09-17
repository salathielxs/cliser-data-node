from node.namespace_manager import (
    create_namespace,
    get_namespace,
    list_namespaces,
    namespace_exists,
    validate_namespace,
    enable_namespace,
    disable_namespace,
    set_namespace_quota,
    require_namespace,
)


def check(condition, message):
    if not condition:
        raise AssertionError(message)


print("=" * 60)
print("CLISER DATA NODE — NAMESPACE TEST")
print("=" * 60)


# validação
check(
    validate_namespace("TEST-NS_01") == "test-ns_01",
    "NORMALIZAÇÃO: FAIL",
)
print("VALIDATION: OK")


# namespace
name = "fase11-test"

if namespace_exists(name):
    raise RuntimeError(
        f"Namespace de teste já existe: {name}"
    )

created = create_namespace(
    name,
    quota_bytes=10 * 1024 * 1024,
)

check(created["namespace"] == name, "CREATE: FAIL")
check(created["status"] == "ACTIVE", "STATUS: FAIL")
check(
    created["quota_bytes"] == 10 * 1024 * 1024,
    "QUOTA: FAIL",
)

print("CREATE: OK")


# existência
check(namespace_exists(name), "EXISTS: FAIL")
print("EXISTS: OK")


# leitura
info = get_namespace(name)

check(info is not None, "GET: FAIL")
check(info["status"] == "ACTIVE", "GET STATUS: FAIL")

print("GET: OK")


# require
required = require_namespace(name)

check(required["namespace"] == name, "REQUIRE: FAIL")

print("REQUIRE ACTIVE: OK")


# disable
disabled = disable_namespace(name)

check(disabled["status"] == "DISABLED", "DISABLE: FAIL")

print("DISABLE: OK")


# require deve bloquear
try:
    require_namespace(name)
except PermissionError:
    print("DISABLED ACCESS BLOCK: OK")
else:
    raise AssertionError(
        "namespace DISABLED deveria bloquear acesso."
    )


# permitir leitura de disabled
allowed = require_namespace(
    name,
    allow_disabled=True,
)

check(
    allowed["status"] == "DISABLED",
    "ALLOW DISABLED: FAIL",
)

print("ALLOW DISABLED: OK")


# enable
enabled = enable_namespace(name)

check(enabled["status"] == "ACTIVE", "ENABLE: FAIL")

print("ENABLE: OK")


# quota
updated = set_namespace_quota(
    name,
    20 * 1024 * 1024,
)

check(
    updated["quota_bytes"] == 20 * 1024 * 1024,
    "QUOTA UPDATE: FAIL",
)

print("QUOTA UPDATE: OK")


# listagem
items = list_namespaces()

check(
    any(x["namespace"] == name for x in items),
    "LIST: FAIL",
)

print("LIST: OK")


active = list_namespaces("ACTIVE")

check(
    any(x["namespace"] == name for x in active),
    "LIST ACTIVE: FAIL",
)

print("LIST ACTIVE: OK")


disabled_list = list_namespaces("DISABLED")

check(
    all(x["status"] == "DISABLED" for x in disabled_list),
    "LIST DISABLED: FAIL",
)

print("LIST DISABLED: OK")


# cleanup
from node.registry import connect

conn = connect()

try:
    conn.execute("BEGIN")

    conn.execute(
        "DELETE FROM quotas WHERE namespace = ?",
        (name,),
    )

    conn.execute(
        "DELETE FROM namespaces WHERE namespace = ?",
        (name,),
    )

    conn.commit()

except Exception:
    conn.rollback()
    raise

finally:
    conn.close()

print("CLEANUP: OK")


print()
print("NAMESPACE LAYER: OK")
print("=" * 60)
