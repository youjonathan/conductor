from conductor import (
    op_proposal_create,
    op_proposal_edit_body,
    op_proposal_set_status,
    op_proposal_read,
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

NEW_BODY = """### Summary
NEW summary.

### Motivation
NEW motivation.

### Scope
- a
- b

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


def test_edit_body_at_drafting_bumps_version(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    pid = op_proposal_create(
        title="t", kind="refactor", executor="builder",
        effort="S", risk="S", risk_note=".", body=SAMPLE_BODY,
    )
    op_proposal_edit_body(id=pid, by="planner", body=NEW_BODY)
    p = op_proposal_read(id=pid, status=None)[0]
    assert p["version"] == 2
    assert "NEW summary." in p["summary"]
    assert p["scope"] == ["a", "b"]
    assert p["status"] == "drafting"  # no state change at 🔵


def test_edit_body_at_awaiting_rejected(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    pid = op_proposal_create(
        title="t", kind="refactor", executor="builder",
        effort="S", risk="S", risk_note=".", body=SAMPLE_BODY,
    )
    op_proposal_set_status(id=pid, new_status="awaiting-jonathan", by="planner")
    try:
        op_proposal_edit_body(id=pid, by="planner", body=NEW_BODY)
    except Exception as exc:
        assert "🟡" in str(exc) or "awaiting" in str(exc).lower()
    else:
        raise AssertionError("expected rejection")


def test_edit_body_at_approved_rejected(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    pid = op_proposal_create(
        title="t", kind="refactor", executor="builder",
        effort="S", risk="S", risk_note=".", body=SAMPLE_BODY,
    )
    op_proposal_set_status(id=pid, new_status="awaiting-jonathan", by="planner")
    op_proposal_set_status(id=pid, new_status="approved", by="human")
    try:
        op_proposal_edit_body(id=pid, by="planner", body=NEW_BODY)
    except Exception as exc:
        assert "approved" in str(exc).lower()
    else:
        raise AssertionError("expected rejection")
