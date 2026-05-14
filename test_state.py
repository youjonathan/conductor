from conductor import (
    op_inbox_append, op_proposal_create, op_proposal_set_status, op_state,
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


def _seed(tmp_path):
    (tmp_path / ".conductor").mkdir()
    (tmp_path / ".conductor" / "inbox.lock").touch()
    (tmp_path / ".conductor" / "proposals.lock").touch()
    (tmp_path / "Conductor Inbox.md").write_text("# Conductor Inbox\n")
    (tmp_path / "Conductor Proposals.md").write_text("# Conductor Proposals\n")


def test_state_empty(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    s = op_state()
    assert s["status_counts"] == {}
    assert s["unacked"] == {"planner": 0, "builder": 0, "human": 0, "codex": 0}


def test_state_counts(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    p1 = op_proposal_create(title="a", kind="refactor", executor="builder",
                            effort="S", risk="S", risk_note=".", body=SAMPLE_BODY)
    op_proposal_create(title="b", kind="drift", executor="planner",
                       effort="S", risk="S", risk_note=".", body=SAMPLE_BODY)
    op_proposal_set_status(id=p1, new_status="awaiting-jonathan", actor="planner")
    s = op_state()
    assert s["status_counts"].get("drafting") == 1
    assert s["status_counts"].get("awaiting-jonathan") == 1
