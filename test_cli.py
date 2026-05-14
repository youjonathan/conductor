import json
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


def _run(args: list[str], cwd: Path, stdin: str = "") -> subprocess.CompletedProcess:
    env = {"PATH": "/usr/bin:/bin", "CONDUCTOR_DIR": str(cwd)}
    return subprocess.run(
        ["python3", str(CONDUCTOR_PY), *args],
        capture_output=True, text=True, input=stdin, env=env,
    )


def _seed_cli(tmp_path: Path):
    (tmp_path / ".conductor").mkdir()
    (tmp_path / ".conductor" / "inbox.lock").touch()
    (tmp_path / ".conductor" / "proposals.lock").touch()
    (tmp_path / "Conductor Inbox.md").write_text("# Conductor Inbox\n")
    (tmp_path / "Conductor Proposals.md").write_text("# Conductor Proposals\n")


def test_cli_inbox_append(tmp_path):
    _seed_cli(tmp_path)
    r = _run(
        ["inbox-append", "--from", "planner", "--to", "builder", "--kind", "note"],
        cwd=tmp_path, stdin="hello",
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "M-0001"


def test_cli_state_returns_json(tmp_path):
    _seed_cli(tmp_path)
    r = _run(["state"], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert "status_counts" in payload
    assert "unacked" in payload


def test_cli_proposal_create_then_read(tmp_path):
    _seed_cli(tmp_path)
    body = (
        "### Summary\ns.\n\n### Motivation\nm.\n\n### Scope\n- a\n\n"
        "### Acceptance\n- b\n\n### Evidence\n- c\n"
    )
    r = _run(
        ["proposal-create", "--title", "T", "--kind", "refactor",
         "--executor", "builder", "--effort", "S", "--risk", "S",
         "--risk-note", "."],
        cwd=tmp_path, stdin=body,
    )
    assert r.returncode == 0, r.stderr
    pid = r.stdout.strip()
    assert pid == "P-001"
    r2 = _run(["proposal-read", "--id", pid], cwd=tmp_path)
    assert r2.returncode == 0, r2.stderr
    payload = json.loads(r2.stdout)
    assert payload[0]["id"] == "P-001"
    assert payload[0]["version"] == 1
