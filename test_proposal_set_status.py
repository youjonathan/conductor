from pathlib import Path

from conductor import (
    op_proposal_create,
    op_proposal_set_status,
    op_proposal_read,
    parse_inbox,
)


SAMPLE_BODY = """### Summary
s.

### Motivation
m.

### Scope
- a

### Acceptance
- b

### Evidence
- c
"""


def _seed(tmp_path: Path):
    (tmp_path / ".conductor").mkdir()
    (tmp_path / ".conductor" / "inbox.lock").touch()
    (tmp_path / ".conductor" / "proposals.lock").touch()
    (tmp_path / "Conductor Inbox.md").write_text("# Conductor Inbox\n")
    (tmp_path / "Conductor Proposals.md").write_text("# Conductor Proposals\n")


def _create(tmp_path, monkeypatch) -> str:
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    return op_proposal_create(
        title="t", kind="refactor", executor="builder",
        effort="S", risk="S", risk_note=".", body=SAMPLE_BODY,
    )


def _converge(pid: str):
    """Helper: simulate convergence so 🔵→🟡 is legal in tests by direct status flip."""
    op_proposal_set_status(id=pid, new_status="awaiting-jonathan", by="planner")


def test_set_status_drafting_to_awaiting_by_planner(tmp_path, monkeypatch):
    pid = _create(tmp_path, monkeypatch)
    op_proposal_set_status(id=pid, new_status="awaiting-jonathan", by="planner")
    p = op_proposal_read(id=pid, status=None)[0]
    assert p["status"] == "awaiting-jonathan"
    msgs = parse_inbox((tmp_path / "Conductor Inbox.md").read_text())
    # An ack message should have been written by the supermutation.
    ack_bodies = [m.body for m in msgs if m.kind.value == "note" and m.proposal == pid]
    assert any("drafting → awaiting-jonathan" in b for b in ack_bodies)


def test_set_status_human_only_rejects_planner(tmp_path, monkeypatch):
    pid = _create(tmp_path, monkeypatch)
    _converge(pid)
    try:
        op_proposal_set_status(id=pid, new_status="approved", by="planner")
    except Exception as exc:
        assert "actor" in str(exc).lower()
    else:
        raise AssertionError("expected FSMError")


def test_set_status_atomic_approval_sets_executor_and_delegation(tmp_path, monkeypatch):
    pid = _create(tmp_path, monkeypatch)
    _converge(pid)
    op_proposal_set_status(
        id=pid, new_status="approved", by="human",
        executor="planner",
        delegated_to="builder",
        delegated_paths=["Projects/VHIL-E/VHIL-E System Design v2.md"],
    )
    p = op_proposal_read(id=pid, status=None)[0]
    assert p["status"] == "approved"
    assert p["executor"] == "planner"
    assert p["delegated_to"] == "builder"
    assert p["delegated_paths"] == ["Projects/VHIL-E/VHIL-E System Design v2.md"]


def test_set_status_same_state_noop(tmp_path, monkeypatch, capsys):
    pid = _create(tmp_path, monkeypatch)
    _converge(pid)
    rc = op_proposal_set_status(id=pid, new_status="awaiting-jonathan", by="planner")
    assert rc == "noop"


def test_set_status_executor_to_in_progress_resets_retry(tmp_path, monkeypatch):
    pid = _create(tmp_path, monkeypatch)
    _converge(pid)
    op_proposal_set_status(id=pid, new_status="approved", by="human")
    op_proposal_set_status(id=pid, new_status="in-progress", by="builder")
    op_proposal_set_status(id=pid, new_status="approved", by="builder")  # retry
    p = op_proposal_read(id=pid, status=None)[0]
    assert p["retry_count"] == 1
    op_proposal_set_status(id=pid, new_status="in-progress", by="builder")
    p2 = op_proposal_read(id=pid, status=None)[0]
    # fresh execution attempt: retry_count resets to 0
    assert p2["retry_count"] == 0


def test_set_status_third_retry_rejected(tmp_path, monkeypatch):
    pid = _create(tmp_path, monkeypatch)
    _converge(pid)
    op_proposal_set_status(id=pid, new_status="approved", by="human")
    op_proposal_set_status(id=pid, new_status="in-progress", by="builder")
    op_proposal_set_status(id=pid, new_status="approved", by="builder")  # retry 1
    op_proposal_set_status(id=pid, new_status="in-progress", by="builder")
    op_proposal_set_status(id=pid, new_status="approved", by="builder")  # retry 2
    op_proposal_set_status(id=pid, new_status="in-progress", by="builder")
    try:
        op_proposal_set_status(id=pid, new_status="approved", by="builder")  # retry 3
    except Exception as exc:
        assert "retry" in str(exc).lower()
    else:
        raise AssertionError("expected retry-cap error")


def test_set_status_pause_records_paused_from(tmp_path, monkeypatch):
    pid = _create(tmp_path, monkeypatch)
    op_proposal_set_status(id=pid, new_status="paused", by="planner")
    p = op_proposal_read(id=pid, status=None)[0]
    assert p["status"] == "paused"
    assert p["status_paused_from"] == "drafting"


def test_set_status_resume_returns_to_paused_from(tmp_path, monkeypatch):
    pid = _create(tmp_path, monkeypatch)
    op_proposal_set_status(id=pid, new_status="paused", by="planner")
    op_proposal_set_status(id=pid, new_status="drafting", by="planner")  # resume
    p = op_proposal_read(id=pid, status=None)[0]
    assert p["status"] == "drafting"
    assert p["status_paused_from"] is None
