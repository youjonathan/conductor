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
    op_proposal_set_status(id=p1, new_status="awaiting-jonathan", by="planner")
    s = op_state()
    assert s["status_counts"].get("drafting") == 1
    assert s["status_counts"].get("awaiting-jonathan") == 1


def test_state_unacked_excludes_self_posted_to_both(tmp_path, monkeypatch):
    """Cycle 2 (2026-05-14) surfaced this: `proposal-set-status` posts a
    `[from: planner → both]` audit note. That note shouldn't show up in
    `unacked.planner` — self-acks aren't meaningful."""
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    # A real cross-role message — should count.
    op_inbox_append(from_="builder", to="planner", kind="note", body="hi",
                    proposal=None, in_reply_to=None, verdict=None, for_version=None)
    # Planner-posted audit message to both — should NOT count toward planner.
    op_inbox_append(from_="planner", to="both", kind="note", body="audit",
                    proposal=None, in_reply_to=None, verdict=None, for_version=None)
    s = op_state()
    assert s["unacked"]["planner"] == 1, s["unacked"]
    # Builder is the recipient of the audit (to=both includes builder) and
    # didn't post it — so it counts toward builder's unacked.
    assert s["unacked"]["builder"] == 1, s["unacked"]
