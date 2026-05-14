from pathlib import Path

from conductor import op_inbox_append, op_inbox_ack, parse_inbox


def _seed(tmp_path: Path):
    (tmp_path / ".conductor").mkdir()
    (tmp_path / ".conductor" / "inbox.lock").touch()
    (tmp_path / ".conductor" / "proposals.lock").touch()
    (tmp_path / "Conductor Inbox.md").write_text("# Conductor Inbox\n")


def test_inbox_ack_creates_ack_message(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    orig = op_inbox_append(
        from_="planner", to="builder", kind="note", body="x",
        proposal=None, re=None, verdict=None, for_version=None,
    )
    ack_id = op_inbox_ack(message_id=orig, by="builder")
    assert ack_id == "M-0002"
    inbox = (tmp_path / "Conductor Inbox.md").read_text()
    msgs = parse_inbox(inbox)
    ack = msgs[1]
    assert ack.kind.value == "ack"
    assert ack.from_.value == "builder"
    assert ack.re == orig


def test_inbox_ack_is_idempotent(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    orig = op_inbox_append(
        from_="planner", to="builder", kind="note", body="x",
        proposal=None, re=None, verdict=None, for_version=None,
    )
    first = op_inbox_ack(message_id=orig, by="builder")
    second = op_inbox_ack(message_id=orig, by="builder")
    assert first == second
    msgs = parse_inbox((tmp_path / "Conductor Inbox.md").read_text())
    ack_count = sum(
        1 for m in msgs if m.kind.value == "ack" and m.re == orig and m.from_.value == "builder"
    )
    assert ack_count == 1
