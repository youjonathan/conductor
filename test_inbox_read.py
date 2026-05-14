from pathlib import Path

from conductor import op_inbox_append, op_inbox_read


def _seed(tmp_path: Path):
    (tmp_path / ".conductor").mkdir()
    (tmp_path / ".conductor" / "inbox.lock").touch()
    (tmp_path / ".conductor" / "proposals.lock").touch()
    inbox = tmp_path / "Conductor Inbox.md"
    inbox.write_text("# Conductor Inbox\n")


def test_inbox_read_returns_all_messages(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    op_inbox_append(from_="planner", to="builder", kind="note", body="a",
                    proposal=None, re=None, verdict=None, for_version=None)
    op_inbox_append(from_="builder", to="planner", kind="note", body="b",
                    proposal=None, re=None, verdict=None, for_version=None)
    msgs = op_inbox_read(role=None, unacked_only=False, since=None, proposal=None)
    assert [m["id"] for m in msgs] == ["M-0001", "M-0002"]


def test_inbox_read_filters_by_role(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    op_inbox_append(from_="planner", to="builder", kind="note", body="for-builder",
                    proposal=None, re=None, verdict=None, for_version=None)
    op_inbox_append(from_="planner", to="human", kind="note", body="for-human",
                    proposal=None, re=None, verdict=None, for_version=None)
    builder_msgs = op_inbox_read(role="builder", unacked_only=False, since=None, proposal=None)
    assert [m["body"] for m in builder_msgs] == ["for-builder"]


def test_inbox_read_filters_by_proposal(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    op_inbox_append(from_="planner", to="builder", kind="note", body="a",
                    proposal="P-001", re=None, verdict=None, for_version=None)
    op_inbox_append(from_="planner", to="builder", kind="note", body="b",
                    proposal="P-002", re=None, verdict=None, for_version=None)
    msgs = op_inbox_read(role=None, unacked_only=False, since=None, proposal="P-001")
    assert [m["body"] for m in msgs] == ["a"]


def test_inbox_read_unacked_only_excludes_acked_messages(tmp_path, monkeypatch):
    """`unacked_only=True` returns messages addressed to the role that lack a
    matching ack from that role. An ack is a `kind: ack` with `re: <id>`."""
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    m1 = op_inbox_append(from_="planner", to="builder", kind="note", body="a",
                         proposal=None, re=None, verdict=None, for_version=None)
    op_inbox_append(
        from_="builder", to="planner", kind="ack", body=f"ack: {m1} by builder",
        proposal=None, re=m1, verdict=None, for_version=None,
    )
    m2 = op_inbox_append(from_="planner", to="builder", kind="note", body="b",
                         proposal=None, re=None, verdict=None, for_version=None)
    msgs = op_inbox_read(role="builder", unacked_only=True, since=None, proposal=None)
    assert [m["id"] for m in msgs] == [m2]


def test_inbox_read_unacked_only_excludes_own_messages(tmp_path, monkeypatch):
    """`unacked_only=True --role X` should not return X's own messages, even
    when they're addressed to `both`. Surfaced in cycle 2 (2026-05-14): the
    `proposal-set-status` supermutation posts a status-transition audit
    `[from: planner → both]`, which then showed up as 'unacked' for the
    Planner herself. Self-acks are not meaningful."""
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    # Foreign message addressed to both — Planner *does* need to see this.
    foreign = op_inbox_append(
        from_="builder", to="both", kind="note", body="hello both",
        proposal=None, re=None, verdict=None, for_version=None,
    )
    # Planner's own audit message to both — Planner should NOT see this as unacked.
    # (The `proposal-set-status` supermutation posts these as `kind: note`.)
    op_inbox_append(
        from_="planner", to="both", kind="note",
        body="P-001 status: drafting → awaiting-jonathan",
        proposal="P-001", re=None, verdict=None, for_version=None,
    )
    msgs = op_inbox_read(role="planner", unacked_only=True, since=None, proposal=None)
    assert [m["id"] for m in msgs] == [foreign]


def test_inbox_read_without_unacked_still_returns_own_messages(tmp_path, monkeypatch):
    """The self-filter only applies when `unacked_only=True`. A normal
    `inbox-read --role planner` still surfaces planner→both messages — they
    show in the timeline; they just don't count as 'awaiting ack from me'."""
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    own = op_inbox_append(
        from_="planner", to="both", kind="note",
        body="audit", proposal="P-001", re=None, verdict=None, for_version=None,
    )
    msgs = op_inbox_read(role="planner", unacked_only=False, since=None, proposal=None)
    assert own in [m["id"] for m in msgs]
