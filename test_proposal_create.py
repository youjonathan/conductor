from pathlib import Path

from conductor import op_proposal_create, parse_proposals


SAMPLE_BODY = """### Summary
The summary.

### Motivation
The motivation.

### Scope
- file_a.py
- file_b.py

### Acceptance
- tests pass

### Evidence
- file_a.py:23
"""


def _seed(tmp_path: Path):
    (tmp_path / ".conductor").mkdir()
    (tmp_path / ".conductor" / "inbox.lock").touch()
    (tmp_path / ".conductor" / "proposals.lock").touch()
    (tmp_path / "Conductor Inbox.md").write_text("# Conductor Inbox\n")
    (tmp_path / "Conductor Proposals.md").write_text("# Conductor Proposals\n")


def test_proposal_create_assigns_p001(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    new_id = op_proposal_create(
        title="Test prop", kind="refactor", executor="builder",
        effort="S", risk="S", risk_note="trivial",
        body=SAMPLE_BODY,
    )
    assert new_id == "P-001"
    props = parse_proposals((tmp_path / "Conductor Proposals.md").read_text())
    assert len(props) == 1
    p = props[0]
    assert p.id == "P-001"
    assert p.version == 1
    assert p.retry_count == 0
    assert p.status.slug == "drafting"
    assert p.scope == ["file_a.py", "file_b.py"]


def test_proposal_create_increments_ids(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    a = op_proposal_create(title="a", kind="feature", executor="builder",
                           effort="S", risk="S", risk_note=".", body=SAMPLE_BODY)
    b = op_proposal_create(title="b", kind="drift", executor="planner",
                           effort="S", risk="S", risk_note=".", body=SAMPLE_BODY)
    assert a == "P-001"
    assert b == "P-002"


def test_proposal_create_rejects_missing_sections(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    bad_body = "### Summary\nonly summary\n"
    try:
        op_proposal_create(
            title="x", kind="feature", executor="builder",
            effort="S", risk="S", risk_note=".", body=bad_body,
        )
    except ValueError as exc:
        assert "section" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError")
