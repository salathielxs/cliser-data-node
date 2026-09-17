from node.registry import list_transactions, get_transaction
from node.recovery import recover_transaction


def find_transaction(states):
    rows = list_transactions()

    for row in rows:
        tx_id = row[0]
        tx = get_transaction(tx_id)

        if tx and tx["state"] in states:
            return tx

    return None


print("=" * 60)
print("G.9.51.2 — RECOVERY IDEMPOTENCY")
print("=" * 60)

for target_state in ("COMMITTED", "ROLLBACK"):
    tx = find_transaction({target_state})

    if tx is None:
        print(f"{target_state}: NÃO ENCONTRADA")
        continue

    tx_id = tx["transaction_id"]
    state_before = tx["state"]

    print()
    print(f"TRANSAÇÃO: {tx_id}")
    print(f"ESTADO: {state_before}")

    result1 = recover_transaction(tx_id)
    after1 = get_transaction(tx_id)

    result2 = recover_transaction(tx_id)
    after2 = get_transaction(tx_id)

    print(f"RECOVERY 1: {result1}")
    print(f"RECOVERY 2: {result2}")
    print(f"ESTADO APÓS 1: {after1['state']}")
    print(f"ESTADO APÓS 2: {after2['state']}")

    assert result1["action"] == "NOOP"
    assert result2["action"] == "NOOP"
    assert after1["state"] == state_before
    assert after2["state"] == state_before

    print(f"IDEMPOTÊNCIA {target_state}: OK")


print()
print("=" * 60)
print("G.9.51.2 — PASS")
print("=" * 60)
