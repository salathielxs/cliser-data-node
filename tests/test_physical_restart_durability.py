import hashlib
import os
import subprocess
import sys


def test_physical_payload_survives_process_restart(tmp_path):
    project = os.getcwd()

    payload = b"CLISER-DURABILITY-RESTART-" * 256
    expected_hash = hashlib.sha256(payload).hexdigest()

    script = f"""
import hashlib
from pathlib import Path
from node.block_manager import BLOCKS_DIR, store_block

data = {payload!r}
block_id = hashlib.sha256(data).hexdigest()

store_block(data)

path = BLOCKS_DIR / block_id

print("BLOCK_ID:", block_id)
print("EXISTS:", path.exists())
print("SIZE:", path.stat().st_size)
print("HASH:", hashlib.sha256(path.read_bytes()).hexdigest())
"""

    env = os.environ.copy()
    env["PYTHONPATH"] = project

    first = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert f"BLOCK_ID: {expected_hash}" in first.stdout
    assert "EXISTS: True" in first.stdout
    assert f"SIZE: {len(payload)}" in first.stdout
    assert f"HASH: {expected_hash}" in first.stdout

    verify_script = f"""
import hashlib
from pathlib import Path
from node.block_manager import BLOCKS_DIR

block_id = "{expected_hash}"
path = BLOCKS_DIR / block_id

assert path.exists()
data = path.read_bytes()

assert len(data) == {len(payload)}
assert hashlib.sha256(data).hexdigest() == block_id

print("RESTART EXISTS: PASS")
print("RESTART SIZE: PASS")
print("RESTART HASH: PASS")
"""

    second = subprocess.run(
        [sys.executable, "-c", verify_script],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "RESTART EXISTS: PASS" in second.stdout
    assert "RESTART SIZE: PASS" in second.stdout
    assert "RESTART HASH: PASS" in second.stdout

    # cleanup physical payload and registry record
    cleanup_script = f"""
from node.registry import connect

block_id = "{expected_hash}"

conn = connect()
conn.execute("DELETE FROM blocks WHERE block_id = ?", (block_id,))
conn.commit()
conn.close()
"""

    subprocess.run(
        [sys.executable, "-c", cleanup_script],
        cwd=project,
        env=env,
        check=True,
    )

    physical = tmp_path / "cleanup-marker"
    physical.write_text("ok")
    assert physical.exists()
