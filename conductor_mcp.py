"""Conductor v2 adapter — FastMCP server exposing the operation surface as MCP tools.

Imports the op_* functions from conductor.py and registers each as a @mcp.tool.
No changes to conductor.py; the file-backed adapter underneath is shared with the
v1 CLI. Both can hit the same CONDUCTOR_DIR concurrently — flock serializes writes.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import NoReturn

from fastmcp import FastMCP

mcp = FastMCP("conductor")


def _fail(msg: str) -> NoReturn:
    """Write a startup error to stderr and exit with code 1."""
    print(f"conductor-mcp: {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    """Validate CONDUCTOR_DIR layout, then start the FastMCP stdio server."""
    cd = os.environ.get("CONDUCTOR_DIR")
    if not cd:
        _fail("CONDUCTOR_DIR is not set")
    cd_path = Path(cd)
    if not cd_path.is_dir():
        _fail(f"CONDUCTOR_DIR={cd!r} is not a directory")
    if not (cd_path / ".conductor").is_dir():
        _fail(f"CONDUCTOR_DIR={cd!r} is missing the .conductor/ subdirectory")
    mcp.run()


if __name__ == "__main__":
    main()
