from conductor import op_proposal_create, op_proposal_read


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


def test_proposal_read_returns_all(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    op_proposal_create(title="a", kind="refactor", executor="builder",
                       effort="S", risk="S", risk_note=".", body=SAMPLE_BODY)
    op_proposal_create(title="b", kind="drift", executor="planner",
                       effort="S", risk="S", risk_note=".", body=SAMPLE_BODY)
    props = op_proposal_read(id=None, status=None)
    assert [p["id"] for p in props] == ["P-001", "P-002"]


def test_proposal_read_filters_by_id(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    op_proposal_create(title="a", kind="refactor", executor="builder",
                       effort="S", risk="S", risk_note=".", body=SAMPLE_BODY)
    op_proposal_create(title="b", kind="drift", executor="planner",
                       effort="S", risk="S", risk_note=".", body=SAMPLE_BODY)
    props = op_proposal_read(id="P-002", status=None)
    assert [p["id"] for p in props] == ["P-002"]
