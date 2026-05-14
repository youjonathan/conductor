import subprocess
from pathlib import Path

CONDUCTOR_PY = Path(__file__).parent / "conductor.py"


def test_help_lists_all_operations():
    result = subprocess.run(
        ["python3", str(CONDUCTOR_PY), "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    expected_ops = [
        "inbox-append", "inbox-read", "inbox-ack",
        "proposal-create", "proposal-read",
        "proposal-edit-body", "proposal-set-status",
        "state",
    ]
    for op in expected_ops:
        assert op in result.stdout, f"missing op {op} in help"
