from node.recovery import recovery_status, recover_pending_transactions

print("=" * 60)
print("G.9.52.1 — RECOVERY PENDING")
print("=" * 60)

before = recovery_status()

print("STATUS ANTES:")
print(before)

results = recover_pending_transactions()

print()
print("RESULTADOS:")
for result in results:
    print(result)

after = recovery_status()

print()
print("STATUS DEPOIS:")
print(after)

assert after["recoverable"] == 0

for result in results:
    assert result["action"] in {"COMMIT", "ROLLBACK"}

print()
print(f"TRANSAÇÕES RECUPERADAS: {len(results)}")
print("RECOVERABLE FINAL: 0")
print("G.9.52.1 — PASS")
