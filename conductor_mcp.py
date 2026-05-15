"""Conductor v2 adapter — FastMCP server exposing the operation surface as MCP tools.

Imports the op_* functions from conductor.py and registers each as a @mcp.tool.
No changes to conductor.py; the file-backed adapter underneath is shared with the
v1 CLI. Both can hit the same CONDUCTOR_DIR concurrently — flock serializes writes.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Annotated, NoReturn

from fastmcp import FastMCP
from pydantic import Field

from conductor import (
    op_state, op_inbox_read, op_inbox_ack, op_inbox_append,
    op_proposal_create, op_proposal_read,
    op_proposal_edit_body, op_proposal_set_status,
)

mcp = FastMCP("conductor")


def _fail(msg: str) -> NoReturn:
    """Write a startup error to stderr and exit with code 1."""
    print(f"conductor-mcp: {msg}", file=sys.stderr)
    raise SystemExit(1)


@mcp.tool
def state() -> dict:
    """Compact JSON summary of bus state for session boot."""
    return op_state()


@mcp.tool
def inbox_read(
    role: str | None = None,
    unacked: bool = False,
    since: str | None = None,
    proposal: str | None = None,
) -> list[dict]:
    """Read inbox messages. Filters: role (`to` matches role or `both`),
    unacked (excludes messages already acked by `role`, and self-posted ones),
    since (id > since), proposal."""
    return op_inbox_read(role=role, unacked=unacked, since=since, proposal=proposal)


@mcp.tool
def inbox_ack(message_id: str, by: str) -> str:
    """Idempotently acknowledge a message. Returns the ack's id, or the existing
    ack's id if `by` has already acked `message_id`."""
    return op_inbox_ack(message_id=message_id, by=by)


@mcp.tool
def inbox_append(
    from_: Annotated[str, Field(alias="from")],
    to: str,
    kind: str,
    body: str,
    proposal: str | None = None,
    in_reply_to: str | None = None,
    verdict: str | None = None,
    for_version: int | None = None,
) -> str:
    """Append a message to the bus. Returns the new M-NNNN id.

    Note: the `from` parameter is aliased — MCP callers send `{"from": ...}`,
    Python sees `from_` internally (since `from` is a reserved keyword).
    """
    return op_inbox_append(
        from_=from_, to=to, kind=kind, body=body,
        proposal=proposal, in_reply_to=in_reply_to,
        verdict=verdict, for_version=for_version,
    )


@mcp.tool
def proposal_create(
    title: str,
    kind: str,
    executor: str,
    effort: str,
    risk: str,
    risk_note: str,
    body: str,
) -> str:
    """Create a new proposal at version=1, status=🔵 drafting. Body must contain
    Summary, Motivation, Scope, Acceptance, Evidence sections."""
    return op_proposal_create(
        title=title, kind=kind, executor=executor,
        effort=effort, risk=risk, risk_note=risk_note, body=body,
    )


@mcp.tool
def proposal_read(
    id: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """Read proposals. Filters: id (exact match), status (slug or emoji)."""
    return op_proposal_read(id=id, status=status)


@mcp.tool
def proposal_edit_body(id: str, by: str, body: str) -> str:
    """Edit a 🔵 drafting proposal's body. Bumps version, invalidates stale
    votes. Returns 'ok'. Raises FSMError if the proposal is not at drafting."""
    return op_proposal_edit_body(id=id, by=by, body=body)


@mcp.tool
def proposal_set_status(
    id: str,
    new_status: str,
    by: str,
    reason: str | None = None,
    executor: str | None = None,
    delegated_to: str | None = None,
    delegated_paths: list[str] | None = None,
) -> str:
    """FSM-validated status transition. Atomic with an audit-note emit to the
    inbox under a two-lock supermutation. Returns 'ok', or 'noop' for same-state
    writes. Raises FSMError for invalid transitions or retry-cap violations."""
    return op_proposal_set_status(
        id=id, new_status=new_status, by=by,
        reason=reason, executor=executor,
        delegated_to=delegated_to, delegated_paths=delegated_paths,
    )


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
