from pathlib import Path

from conductor import op_inbox_append, parse_inbox


def _seed_inbox(tmp_path: Path) -> Path:
    (tmp_path / ".conductor").mkdir()
    (tmp_path / ".conductor" / "inbox.lock").touch()
    (tmp_path / ".conductor" / "proposals.lock").touch()
    inbox = tmp_path / "Conductor Inbox.md"
    inbox.write_text(
        "# Conductor Inbox\n\nAppend-only.\n"
        "\n## M-0001 [from: human → both] 2026-05-14T00:00:00Z\n"
        "[kind: note]\n\nseed.\n"
    )
    return inbox


def test_inbox_append_assigns_next_id(tmp_path, monkeypatch):
    inbox = _seed_inbox(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    new_id = op_inbox_append(
        from_="planner", to="builder", kind="scan-result",
        body="Found 3 items.",
        proposal=None, in_reply_to=None, verdict=None, for_version=None,
    )
    assert new_id == "M-0002"
    msgs = parse_inbox(inbox.read_text())
    assert len(msgs) == 2
    assert msgs[1].id == "M-0002"
    assert msgs[1].body.strip() == "Found 3 items."


def test_inbox_append_review_requires_verdict_when_proposal_set(tmp_path, monkeypatch):
    _seed_inbox(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    try:
        op_inbox_append(
            from_="builder", to="planner", kind="review",
            body="x", proposal="P-001",
            in_reply_to=None, verdict=None, for_version=None,
        )
    except ValueError as exc:
        assert "verdict" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError")


def test_inbox_append_monotonic_under_load(tmp_path, monkeypatch):
    _seed_inbox(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    ids = [
        op_inbox_append(
            from_="planner", to="builder", kind="note", body=f"n{i}",
            proposal=None, in_reply_to=None, verdict=None, for_version=None,
        )
        for i in range(5)
    ]
    assert ids == ["M-0002", "M-0003", "M-0004", "M-0005", "M-0006"]
