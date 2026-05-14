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
