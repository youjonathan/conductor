"""Tests for conductor_mcp — the FastMCP wrapper over conductor.py's op_* functions."""
from pathlib import Path

import pytest


def _seed(tmp_path: Path) -> None:
    """Set up a minimal CONDUCTOR_DIR layout that satisfies the adapter."""
    (tmp_path / ".conductor").mkdir()
    (tmp_path / ".conductor" / "inbox.lock").touch()
    (tmp_path / ".conductor" / "proposals.lock").touch()
    (tmp_path / "Conductor Inbox.md").write_text("# Conductor Inbox\n")
    (tmp_path / "Conductor Proposals.md").write_text("# Conductor Proposals\n")


# --- Fail-fast boot validation ---

def test_main_exits_when_conductor_dir_unset(monkeypatch, capsys):
    monkeypatch.delenv("CONDUCTOR_DIR", raising=False)
    import conductor_mcp
    with pytest.raises(SystemExit) as exc:
        conductor_mcp.main()
    assert exc.value.code == 1
    assert "CONDUCTOR_DIR is not set" in capsys.readouterr().err


def test_main_exits_when_conductor_dir_not_a_directory(tmp_path, monkeypatch, capsys):
    bogus = tmp_path / "does-not-exist"
    monkeypatch.setenv("CONDUCTOR_DIR", str(bogus))
    import conductor_mcp
    with pytest.raises(SystemExit) as exc:
        conductor_mcp.main()
    assert exc.value.code == 1
    assert "is not a directory" in capsys.readouterr().err


def test_main_exits_when_dot_conductor_subdir_missing(tmp_path, monkeypatch, capsys):
    # Valid CONDUCTOR_DIR but no .conductor/ subdir
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    import conductor_mcp
    with pytest.raises(SystemExit) as exc:
        conductor_mcp.main()
    assert exc.value.code == 1
    assert ".conductor/ subdirectory" in capsys.readouterr().err


# --- Direct wrapper tests (one per tool) ---

def test_state_returns_dict(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    from conductor_mcp import state
    result = state()
    assert isinstance(result, dict)
    assert "status_counts" in result
    assert "unacked" in result
    assert "last_activity" in result
    assert "in_progress" in result
    assert "retry_counts" in result


def test_inbox_read_returns_list(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    from conductor_mcp import inbox_read
    result = inbox_read()
    assert result == []  # empty bus

def test_inbox_read_filters_by_role(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    from conductor import op_inbox_append
    from conductor_mcp import inbox_read
    op_inbox_append(
        from_="planner", to="builder", kind="note", body="hi",
        proposal=None, in_reply_to=None, verdict=None, for_version=None,
    )
    result = inbox_read(role="builder")
    assert len(result) == 1
    assert result[0]["to"] == "builder"

def test_inbox_ack_creates_ack(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    from conductor import op_inbox_append
    from conductor_mcp import inbox_ack
    orig = op_inbox_append(
        from_="planner", to="builder", kind="note", body="hi",
        proposal=None, in_reply_to=None, verdict=None, for_version=None,
    )
    ack_id = inbox_ack(message_id=orig, by="builder")
    assert ack_id.startswith("M-")
    assert ack_id != orig


def test_inbox_append_direct_call(tmp_path, monkeypatch):
    """Direct Python call uses the `from_` parameter name (since Python sees
    the raw kwarg, not the Pydantic alias)."""
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    from conductor_mcp import inbox_append
    msg_id = inbox_append(
        from_="planner", to="builder", kind="note", body="hello",
    )
    assert msg_id == "M-0001"


# --- Alias test (through FastMCP Client; the only path where Pydantic alias
#     validation runs) ---

async def test_inbox_append_accepts_from_alias_via_client(tmp_path, monkeypatch):
    """The MCP tool schema must accept `from` (the alias), not `from_`.
    Direct Python call uses `from_` because Pydantic alias only fires during
    FastMCP's tool invocation pipeline, not on raw Python calls."""
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))
    from fastmcp import Client
    from conductor_mcp import mcp
    async with Client(mcp) as client:
        result = await client.call_tool(
            "inbox_append",
            {"from": "planner", "to": "builder", "kind": "note", "body": "hi"},
        )
    # FastMCP wraps the str return; .data exposes it
    assert result.data == "M-0001"
