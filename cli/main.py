import hashlib
import sys
from pathlib import Path


# ============================================================
# BASE
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


# ============================================================
# NODE
# ============================================================

from node.identity import load_identity
from node.storage import OBJECTS_DIR
from node.metrics import storage_metrics, namespace_metrics
from node.registry import (
    get_object,
    list_objects,
    count_objects,
    all_objects,
    get_namespace,
    list_namespace_records,
    set_namespace_status,
    list_objects_by_namespace,
)
from node.quota import (
    set_quota,
    quota_report,
)
from node.namespace_manager import create_namespace
from node.manifest import (
    get_manifest,
    reconstruct_object,
)
from node.health import run_health
from node.object_manager import (
    put_object,
    get_object_data,
    verify_object,
    delete_object_data,
    garbage_collect,
    reconcile_storage,
)


# ============================================================
# NODE
# ============================================================

def status():
    try:
        identity_data = load_identity()
    except Exception as exc:
        print(
            f"Erro ao carregar identidade: "
            f"{type(exc).__name__}: {exc}"
        )
        return

    print("=== CLISER DATA NODE ===")
    print(f"Node ID:    {identity_data['node_id']}")
    print(f"Role:       {identity_data['role']}")
    print(f"Version:    {identity_data['version']}")
    print(f"Objects:    {count_objects()}")
    print(f"Storage:    {OBJECTS_DIR}")


def identity():
    try:
        data = load_identity()
    except Exception as exc:
        print(
            f"Erro ao carregar identidade: "
            f"{type(exc).__name__}: {exc}"
        )
        return

    print("=== CLISER IDENTITY ===")
    print(f"Node ID:     {data['node_id']}")
    print(f"Role:        {data['role']}")
    print(f"Version:     {data['version']}")
    print(f"Fingerprint: {data['fingerprint']}")


# ============================================================
# HEALTH
# ============================================================

def health():
    print("=== CLISER DATA NODE HEALTH ===")

    try:
        result = run_health()
    except Exception as exc:
        print(
            f"Health check falhou: "
            f"{type(exc).__name__}: {exc}"
        )
        return

    checks = result["checks"]

    for name, check in checks.items():
        status_value = check.get(
            "status",
            "UNKNOWN",
        )

        print(
            f"{name.upper():<12} "
            f"{status_value}"
        )

        if "detail" in check:
            print(
                f"  {check['detail']}"
            )

    print()
    print("=== HEALTH SUMMARY ===")

    objects_data = checks["objects"]
    namespaces = checks["namespaces"]
    capacity = checks["capacity"]

    print(
        f"Namespaces:      "
        f"{namespaces.get('total', 0)}"
    )

    print(
        f"Active:          "
        f"{namespaces.get('active', 0)}"
    )

    print(
        f"Objects:         "
        f"{objects_data.get('total', 0)}"
    )

    print(
        f"Active Objects:  "
        f"{objects_data.get('active', 0)}"
    )

    print(
        f"Direct Objects:  "
        f"{objects_data.get('direct', 0)}"
    )

    print(
        f"Block Objects:   "
        f"{objects_data.get('blocks', 0)}"
    )

    print(
        f"Deleted Objects: "
        f"{objects_data.get('deleted', 0)}"
    )

    print(
        f"Capacity State:  "
        f"{capacity.get('state', 'UNKNOWN')}"
    )

    print()
    print(
        f"HEALTH: "
        f"{result['status']}"
    )


# ============================================================
# OBJECTS
# ============================================================

def put(data, namespace="default"):
    try:
        obj = put_object(
            data.encode("utf-8"),
            namespace=namespace,
        )
    except Exception as exc:
        print(
            f"PUT BLOQUEADO: "
            f"{type(exc).__name__}: {exc}"
        )
        return

    print("=== OBJECT STORED ===")
    print(
        f"Object ID:  "
        f"{obj['object_id']}"
    )
    print(
        f"Namespace:  "
        f"{obj['namespace']}"
    )
    print(
        f"Size:       "
        f"{obj['size']} bytes"
    )
    print(
        f"Status:     "
        f"{obj['status']}"
    )
    print(
        f"Mode:       "
        f"{obj['storage_mode']}"
    )

    if obj["storage_mode"] == "BLOCKS":
        print(
            f"Blocks:     "
            f"{obj['block_count']}"
        )


def get(object_id):
    try:
        data = get_object_data(
            object_id
        )
        print(
            data.decode("utf-8")
        )
    except (
        FileNotFoundError,
        ValueError,
    ) as exc:
        print(
            f"Erro: {exc}"
        )


def inspect(object_id):
    obj = get_object(object_id)

    if obj is None:
        print(
            "Objeto não encontrado "
            "no Registry."
        )
        return

    print("=== OBJECT ===")
    print(
        f"Object ID:     "
        f"{obj['object_id']}"
    )
    print(
        f"Content Hash:  "
        f"{obj['content_hash']}"
    )
    print(
        f"Namespace:     "
        f"{obj.get('namespace', 'default')}"
    )
    print(
        f"Size:          "
        f"{obj['size']} bytes"
    )
    print(
        f"Storage:       "
        f"{obj['storage_path']}"
    )
    print(
        f"Created:       "
        f"{obj['created_at']}"
    )
    print(
        f"Status:        "
        f"{obj['status']}"
    )


def verify(object_id):
    try:
        ok, status_value = (
            verify_object(object_id)
        )
    except Exception as exc:
        print(
            f"Erro: {type(exc).__name__}: "
            f"{exc}"
        )
        return

    print("=== OBJECT INTEGRITY ===")
    print(
        f"Object ID: {object_id}"
    )
    print(
        f"Status:    {status_value}"
    )

    if ok:
        print("Integrity: OK")
    else:
        print("Integrity: FAILED")


def delete(object_id):
    try:
        ok, status_value = (
            delete_object_data(object_id)
        )
    except Exception as exc:
        print(
            f"Erro: {type(exc).__name__}: "
            f"{exc}"
        )
        return

    print("=== OBJECT DELETE ===")
    print(
        f"Object ID: {object_id}"
    )
    print(
        f"Status:    {status_value}"
    )


def objects(namespace=None):
    try:
        if namespace:
            rows = (
                list_objects_by_namespace(
                    namespace
                )
            )
        else:
            rows = list_objects()
    except Exception as exc:
        print(
            f"Erro: {type(exc).__name__}: "
            f"{exc}"
        )
        return

    print("=== OBJECT REGISTRY ===")

    if not rows:
        print(
            "Nenhum objeto registrado."
        )
        return

    for row in rows:
        print()

        if isinstance(row, dict):
            print(
                f"ID:        "
                f"{row['object_id']}"
            )
            print(
                f"Namespace: "
                f"{row.get('namespace', 'default')}"
            )
            print(
                f"Size:      "
                f"{row['size']} bytes"
            )
            print(
                f"Created:   "
                f"{row['created_at']}"
            )
            print(
                f"Status:    "
                f"{row['status']}"
            )

        else:
            print(
                f"ID:        {row[0]}"
            )
            print(
                f"Size:      {row[1]} bytes"
            )
            print(
                f"Namespace: {row[2]}"
            )
            print(
                f"Created:   {row[3]}"
            )
            print(
                f"Status:    {row[4]}"
            )


# ============================================================
# STORAGE
# ============================================================

def gc():
    print("=== GARBAGE COLLECTOR ===")

    try:
        result = garbage_collect()
    except Exception as exc:
        print(
            f"Erro: {type(exc).__name__}: "
            f"{exc}"
        )
        return

    print(
        f"Objects removed: "
        f"{result.get('removed_objects', 0)}"
    )
    print(
        f"Blocks removed:  "
        f"{result.get('removed_blocks', 0)}"
    )
    print(
        f"Errors:          "
        f"{len(result.get('errors', []))}"
    )

    if result.get("errors"):
        print()
        print("=== ERRORS ===")

        for error in result["errors"]:
            print(error)


def reconcile():
    try:
        recovered = reconcile_storage()
    except Exception as exc:
        print(
            f"Erro: {type(exc).__name__}: "
            f"{exc}"
        )
        return

    print("=== STORAGE RECONCILIATION ===")
    print(
        f"Recovered: {recovered}"
    )


def consistency():
    print("=== STORAGE CONSISTENCY ===")

    try:
        rows = all_objects()
    except Exception as exc:
        print(
            f"Erro: {type(exc).__name__}: "
            f"{exc}"
        )
        return

    registered_objects = set()

    missing = 0
    ok = 0
    block_objects = 0
    direct_objects = 0

    for row in rows:
        object_id = row[0]
        content_hash = row[1]
        size = row[2]
        storage_path = row[3]
        status_value = row[-1]

        registered_objects.add(
            object_id
        )

        if status_value != "ACTIVE":
            continue

        # ----------------------------------------------------
        # BLOCK OBJECT
        # ----------------------------------------------------

        if storage_path is None:
            block_objects += 1

            try:
                manifest = get_manifest(
                    object_id
                )

                if manifest is None:
                    print(
                        f"MISSING_MANIFEST: "
                        f"{object_id}"
                    )
                    missing += 1
                    continue

                if manifest["status"] != "ACTIVE":
                    print(
                        f"INVALID_MANIFEST: "
                        f"{object_id}"
                    )
                    missing += 1
                    continue

                data = reconstruct_object(
                    object_id
                )

                if len(data) != size:
                    print(
                        f"SIZE_MISMATCH: "
                        f"{object_id}"
                    )
                    missing += 1
                    continue

                calculated_hash = (
                    hashlib.sha256(data)
                    .hexdigest()
                )

                if calculated_hash != content_hash:
                    print(
                        f"HASH_MISMATCH: "
                        f"{object_id}"
                    )
                    missing += 1
                    continue

                print(
                    f"BLOCK_OBJECT: "
                    f"{object_id}"
                )

                ok += 1

            except Exception as exc:
                print(
                    f"BLOCK_ERROR: "
                    f"{object_id} "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )
                missing += 1

            continue

        # ----------------------------------------------------
        # DIRECT OBJECT
        # ----------------------------------------------------

        direct_objects += 1

        path = Path(storage_path)

        if not path.exists():
            print(
                f"MISSING_OBJECT: "
                f"{object_id}"
            )
            missing += 1
            continue

        if path.stat().st_size != size:
            print(
                f"SIZE_MISMATCH: "
                f"{object_id}"
            )
            missing += 1
            continue

        try:
            data = path.read_bytes()

            calculated_hash = (
                hashlib.sha256(data)
                .hexdigest()
            )

            if calculated_hash != content_hash:
                print(
                    f"HASH_MISMATCH: "
                    f"{object_id}"
                )
                missing += 1
                continue

        except Exception as exc:
            print(
                f"READ_ERROR: "
                f"{object_id} "
                f"{type(exc).__name__}: "
                f"{exc}"
            )
            missing += 1
            continue

        print(
            f"DIRECT_OBJECT: "
            f"{object_id}"
        )

        ok += 1

    # --------------------------------------------------------
    # PHYSICAL ORPHANS
    # --------------------------------------------------------

    orphan = 0

    if OBJECTS_DIR.exists():
        for physical_path in (
            OBJECTS_DIR.iterdir()
        ):
            if (
                physical_path.is_file()
                and physical_path.name
                not in registered_objects
            ):
                print(
                    f"ORPHAN_OBJECT: "
                    f"{physical_path.name}"
                )
                orphan += 1

    print()
    print("=== CONSISTENCY SUMMARY ===")
    print(
        f"Objects checked: {ok}"
    )
    print(
        f"Direct objects:  "
        f"{direct_objects}"
    )
    print(
        f"Block objects:   "
        f"{block_objects}"
    )
    print(
        f"Missing/errors:   "
        f"{missing}"
    )
    print(
        f"Orphans:         "
        f"{orphan}"
    )


# ============================================================
# NAMESPACE
# ============================================================

def namespace_list():
    try:
        rows = list_namespace_records()
    except Exception as exc:
        print(
            f"Erro: {type(exc).__name__}: "
            f"{exc}"
        )
        return

    print("=== CLISER NAMESPACES ===")

    if not rows:
        print(
            "Nenhum namespace registrado."
        )
        return

    for row in rows:
        print()
        print(
            f"Namespace: {row['namespace']}"
        )
        print(
            f"Status:    {row['status']}"
        )
        print(
            f"Quota:     {row['quota_bytes']} bytes"
        )
        print(
            f"Created:   {row['created_at']}"
        )
        print(
            f"Updated:   {row['updated_at']}"
        )


def namespace_create(
    namespace,
    quota_bytes=0,
):
    try:
        create_namespace(
            namespace,
            quota_bytes=quota_bytes,
        )

        result = get_namespace(
            namespace
        )

        if result is None:
            raise RuntimeError(
                "Namespace não foi encontrado "
                f"após criação: {namespace}"
            )

    except Exception as exc:
        print(
            f"Erro: {type(exc).__name__}: "
            f"{exc}"
        )
        return

    print("=== NAMESPACE CREATED ===")
    print(
        f"Namespace: "
        f"{result['namespace']}"
    )
    print(
        f"Status:    "
        f"{result['status']}"
    )
    print(
        f"Quota:     "
        f"{result['quota_bytes']} bytes"
    )


def namespace_status(namespace):
    try:
        data = get_namespace(
            namespace
        )
    except Exception as exc:
        print(
            f"Erro: {type(exc).__name__}: "
            f"{exc}"
        )
        return

    if data is None:
        print(
            f"Namespace não encontrado: "
            f"{namespace}"
        )
        return

    print("=== NAMESPACE ===")
    print(
        f"Namespace: {data['namespace']}"
    )
    print(
        f"Status:    {data['status']}"
    )
    print(
        f"Quota:     {data['quota_bytes']} bytes"
    )
    print(
        f"Created:   {data['created_at']}"
    )
    print(
        f"Updated:   {data['updated_at']}"
    )


def namespace_set_status(
    namespace,
    status_value,
):
    try:
        set_namespace_status(
            namespace,
            status_value,
        )
    except Exception as exc:
        print(
            f"Erro: {type(exc).__name__}: "
            f"{exc}"
        )
        return

    print("=== NAMESPACE STATUS ===")
    print(
        f"Namespace: {namespace}"
    )
    print(
        f"Status:    {status_value}"
    )


# ============================================================
# QUOTA
# ============================================================

def quota_show(namespace):
    try:
        report = quota_report(
            namespace
        )
    except Exception as exc:
        print(
            f"Erro: {type(exc).__name__}: "
            f"{exc}"
        )
        return

    print("=== CLISER QUOTA ===")
    print(
        f"Namespace: "
        f"{report['namespace']}"
    )
    print(
        f"Quota:     "
        f"{report['quota_bytes']} bytes"
    )
    print(
        f"Used:      "
        f"{report['used_bytes']} bytes"
    )
    print(
        f"Available: "
        f"{report['available_bytes']} bytes"
    )
    print(
        f"State:     "
        f"{report['state']}"
    )


def quota_set(
    namespace,
    quota_bytes,
):
    try:
        quota_bytes = int(
            quota_bytes
        )

        if quota_bytes < 0:
            raise ValueError(
                "quota não pode ser negativa."
            )

        result = set_quota(
            namespace,
            quota_bytes,
        )

    except Exception as exc:
        print(
            f"Erro: {type(exc).__name__}: "
            f"{exc}"
        )
        return

    print("=== QUOTA UPDATED ===")
    print(
        f"Namespace: {namespace}"
    )
    print(
        f"Quota:     "
        f"{result['quota_bytes']} bytes"
    )


# ============================================================
# METRICS
# ============================================================

def metrics(namespace=None):
    if namespace:
        try:
            result = namespace_metrics(namespace)
        except Exception as exc:
            print(
                f"Erro ao calcular métricas do namespace: "
                f"{type(exc).__name__}: {exc}"
            )
            return

        print("=== NAMESPACE METRICS ===")
        print()
        print(f"Namespace: {result['namespace']}")
        print(f"Status:    {result['status']}")
        print()

        print("OBJECTS")
        print(f"Total:          {result['objects']['total']}")
        print(f"Direct:         {result['objects']['direct']}")
        print(f"Block:          {result['objects']['block']}")
        print(
            f"Logical:        "
            f"{result['objects']['logical_bytes']} bytes"
        )
        print()

        print("MANIFESTS")
        print(f"Active:         {result['manifests']}")
        print()

        blocks = result["blocks"]

        print("BLOCKS")
        print(f"References:     {blocks['references']}")
        print(f"Unique:         {blocks['unique_blocks']}")
        print(
            f"Referenced:     "
            f"{blocks['referenced_bytes']} bytes"
        )
        print(
            f"Unique Physical:"
            f" {blocks['unique_physical_bytes']} bytes"
        )
        print(
            f"Attributed:     "
            f"{blocks['attributed_physical_bytes']} bytes"
        )
        print(f"Shared:         {blocks['shared_blocks']}")
        print()

        dedup = result["deduplication"]

        print("DEDUPLICATION")
        print(
            f"Savings:        "
            f"{dedup['savings_bytes']} bytes"
        )
        print(f"Ratio:          {dedup['ratio']}x")
        print(
            f"Savings:        "
            f"{dedup['savings_percent']} %"
        )
        print()

        quota = result["quota"]

        print("QUOTA")
        print(f"Used:           {quota['used_bytes']} bytes")

        if quota.get("quota_bytes", 0) == 0:
            print("Available:      UNLIMITED")
        else:
            print(
                f"Available:      "
                f"{quota['available_bytes']} bytes"
            )

        print(f"State:          {quota['state']}")
        print()

        print("CAPACITY")
        print(
            f"Global State:   "
            f"{result['capacity']['state']}"
        )
        print(
            f"Global Free:    "
            f"{result['capacity']['free_bytes']} bytes"
        )
        return

    try:
        result = storage_metrics()
    except Exception as exc:
        print(
            f"Erro ao calcular métricas: "
            f"{type(exc).__name__}: {exc}"
        )
        return

    print("=== CLISER STORAGE METRICS ===")
    print()

    print("OBJECTS")
    print(f"Total:   {result['objects']['total']}")
    print(f"Logical: {result['objects']['logical_bytes']} bytes")
    print()

    print("DIRECT")
    print(f"Count:   {result['direct']['count']}")
    print(f"Logical: {result['direct']['logical_bytes']} bytes")
    print()

    print("BLOCK OBJECTS")
    print(f"Count:   {result['block_objects']['count']}")
    print(
        f"Logical: "
        f"{result['block_objects']['logical_bytes']} bytes"
    )
    print()

    print("BLOCKS")
    print(f"Unique:      {result['blocks']['unique']}")
    print(
        f"Physical:    "
        f"{result['blocks']['physical_bytes']} bytes"
    )
    print(
        f"Referenced:  "
        f"{result['blocks']['referenced_bytes']} bytes"
    )
    print(
        f"Shared:      "
        f"{result['blocks']['shared_blocks']}"
    )
    print()

    print("DEDUPLICATION")
    print(
        f"Savings:     "
        f"{result['deduplication']['savings_bytes']} bytes"
    )
    print(
        f"Ratio:       "
        f"{result['deduplication']['ratio']}x"
    )
    print(
        f"Savings:     "
        f"{result['deduplication']['savings_percent']} %"
    )
    print()

    capacity = result["capacity"]
    filesystem = capacity["filesystem"]
    cliser_capacity = capacity["cliser_capacity"]

    print("CAPACITY")
    print(
        f"Total:       "
        f"{filesystem['total_bytes']} bytes"
    )
    print(
        f"Free:        "
        f"{filesystem['free_bytes']} bytes"
    )
    print(
        f"CLISER Used: "
        f"{cliser_capacity['used_bytes']} bytes"
    )
    print(
        f"State:       "
        f"{cliser_capacity['state']}"
    )


def help_command():
    print("""
=== CLISER DATA NODE CLI ===

NODE
  status
  identity
  health

OBJECTS
  put "<dados>" [namespace]
  get <object_id>
  inspect <object_id>
  verify <object_id>
  delete <object_id>
  objects [namespace]

NAMESPACE
  namespace list
  namespace create <nome> [quota_bytes]
  namespace status <nome>
  namespace enable <nome>
  namespace disable <nome>

QUOTA
  quota show <namespace>
  quota set <namespace> <bytes>

STORAGE
  consistency
  reconcile
  gc

METRICS
  metrics
  metrics namespace <nome>
""")


# ============================================================
# MAIN
# ============================================================

def main():

    if len(sys.argv) < 2:
        help_command()
        return

    command = sys.argv[1]

    # --------------------------------------------------------
    # HEALTH
    # --------------------------------------------------------

    if command == "health":
        health()
        return

    # --------------------------------------------------------
    # NODE
    # --------------------------------------------------------

    if command == "status":
        status()
        return

    if command == "identity":
        identity()
        return

    # --------------------------------------------------------
    # OBJECTS
    # --------------------------------------------------------

    if command == "put":

        if len(sys.argv) < 3:
            print(
                'Uso: python -m cli.main '
                'put "dados" [namespace]'
            )
            return

        if len(sys.argv) >= 4:
            namespace = sys.argv[-1]
            data = " ".join(
                sys.argv[2:-1]
            )
        else:
            namespace = "default"
            data = sys.argv[2]

        put(
            data,
            namespace,
        )
        return

    if command == "get":

        if len(sys.argv) < 3:
            print(
                "Uso: python -m cli.main "
                "get <object_id>"
            )
            return

        get(sys.argv[2])
        return

    if command == "inspect":

        if len(sys.argv) < 3:
            print(
                "Uso: python -m cli.main "
                "inspect <object_id>"
            )
            return

        inspect(sys.argv[2])
        return

    if command == "verify":

        if len(sys.argv) < 3:
            print(
                "Uso: python -m cli.main "
                "verify <object_id>"
            )
            return

        verify(sys.argv[2])
        return

    if command == "delete":

        if len(sys.argv) < 3:
            print(
                "Uso: python -m cli.main "
                "delete <object_id>"
            )
            return

        delete(sys.argv[2])
        return

    if command == "objects":

        namespace = (
            sys.argv[2]
            if len(sys.argv) >= 3
            else None
        )

        objects(namespace)
        return

    # --------------------------------------------------------
    # STORAGE
    # --------------------------------------------------------

    if command == "consistency":
        consistency()
        return

    if command == "gc":
        gc()
        return

    if command == "reconcile":
        reconcile()
        return

    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    if command == "metrics":

        if (
            len(sys.argv) >= 3
            and sys.argv[2] == "namespace"
        ):
            if len(sys.argv) < 4:
                print(
                    "Uso: python -m cli.main "
                    "metrics namespace <nome>"
                )
                return

            metrics(
                namespace=sys.argv[3]
            )
            return

        metrics()
        return

    # --------------------------------------------------------
    # NAMESPACE
    # --------------------------------------------------------

    if command == "namespace":

        if len(sys.argv) < 3:
            print(
                "Uso: namespace "
                "[list|create|status|enable|disable]"
            )
            return

        subcommand = sys.argv[2]

        if subcommand == "list":
            namespace_list()
            return

        if subcommand == "create":

            if len(sys.argv) < 4:
                print(
                    "Uso: namespace create "
                    "<nome> [quota_bytes]"
                )
                return

            namespace = sys.argv[3]

            try:
                quota_bytes = (
                    int(sys.argv[4])
                    if len(sys.argv) >= 5
                    else 0
                )
            except ValueError:
                print(
                    "Erro: quota_bytes deve "
                    "ser um número inteiro."
                )
                return

            namespace_create(
                namespace,
                quota_bytes,
            )
            return

        if subcommand == "status":

            if len(sys.argv) < 4:
                print(
                    "Uso: namespace status "
                    "<nome>"
                )
                return

            namespace_status(
                sys.argv[3]
            )
            return

        if subcommand == "enable":

            if len(sys.argv) < 4:
                print(
                    "Uso: namespace enable "
                    "<nome>"
                )
                return

            namespace_set_status(
                sys.argv[3],
                "ACTIVE",
            )
            return

        if subcommand == "disable":

            if len(sys.argv) < 4:
                print(
                    "Uso: namespace disable "
                    "<nome>"
                )
                return

            namespace_set_status(
                sys.argv[3],
                "DISABLED",
            )
            return

        print(
            f"Subcomando desconhecido: "
            f"{subcommand}"
        )
        return

    # --------------------------------------------------------
    # QUOTA
    # --------------------------------------------------------

    if command == "quota":

        if len(sys.argv) < 3:
            print(
                "Uso: quota [show|set]"
            )
            return

        subcommand = sys.argv[2]

        if subcommand == "show":

            if len(sys.argv) < 4:
                print(
                    "Uso: quota show "
                    "<namespace>"
                )
                return

            quota_show(
                sys.argv[3]
            )
            return

        if subcommand == "set":

            if len(sys.argv) < 5:
                print(
                    "Uso: quota set "
                    "<namespace> <bytes>"
                )
                return

            quota_set(
                sys.argv[3],
                sys.argv[4],
            )
            return

        print(
            f"Subcomando desconhecido: "
            f"{subcommand}"
        )
        return

    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

    print(
        f"Comando desconhecido: "
        f"{command}"
    )
    print()
    help_command()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
