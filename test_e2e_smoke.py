"""End-to-end smoke test: one full proposal lifecycle through adapter ops.

Simulates what a Planner + Builder + human + Codex would do, calling
adapter ops in order. Asserts the final state is what §6.1 (Cycle A) describes.
"""
from pathlib import Path

from conductor import (
    op_inbox_append, op_inbox_ack, op_inbox_read,
    op_proposal_create, op_proposal_set_status, op_proposal_read,
    op_state,
)


SAMPLE_BODY = """### Summary
Remove dead RetrieverV1 import shim.

### Motivation
Dead code; misleads contributors.

### Scope
- vhile/retrieval/__init__.py

### Acceptance
- pytest passes

### Evidence
- vhile/retrieval/__init__.py:23
"""


def _seed(tmp_path: Path):
    (tmp_path / ".conductor").mkdir()
    (tmp_path / ".conductor" / "inbox.lock").touch()
    (tmp_path / ".conductor" / "proposals.lock").touch()
    (tmp_path / "Conductor Inbox.md").write_text("# Conductor Inbox\n")
    (tmp_path / "Conductor Proposals.md").write_text("# Conductor Proposals\n")


def test_full_cycle_code_refactor(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))

    # T+2 — Planner scans
    pid = op_proposal_create(
        title="Remove dead RetrieverV1", kind="refactor", executor="builder",
        effort="S", risk="S", risk_note="trivial deletion", body=SAMPLE_BODY,
    )
    op_inbox_append(
        from_="planner", to="builder", kind="scan-result", body="Found 1.",
        proposal=pid, re=None, verdict=None, for_version=None,
    )

    # T+8 — Builder reviews
    op_inbox_append(
        from_="builder", to="planner", kind="review",
        body="Confirmed; scope ok.",
        proposal=pid, re=None,
        verdict="approved-for-human", for_version=1,
    )

    # T+11 — Planner votes; convergence
    op_inbox_append(
        from_="planner", to="builder", kind="review",
        body="Agree; promoting.",
        proposal=pid, re=None,
        verdict="approved-for-human", for_version=1,
    )
    op_proposal_set_status(id=pid, new_status="awaiting-jonathan", actor="planner")

    # T+14 — Human approves
    op_proposal_set_status(id=pid, new_status="approved", actor="human")

    # T+17 — Builder starts execution
    op_proposal_set_status(id=pid, new_status="in-progress", actor="builder")
    handoff_id = op_inbox_append(
        from_="builder", to="codex", kind="note",
        body="[Codex handoff doc per §7.2]",
        proposal=pid, re=None, verdict=None, for_version=None,
    )

    # T+34 — Codex returns
    op_inbox_append(
        from_="codex", to="builder", kind="note",
        body="status: success; pr_url: https://github.com/.../1234",
        proposal=pid, re=handoff_id, verdict=None, for_version=None,
    )
    op_inbox_append(
        from_="builder", to="human", kind="review",
        body="Verified; ready-to-merge.",
        proposal=pid, re=None,
        verdict="approved-for-human", for_version=1,
    )

    # T+45 — Human merges; Builder closes
    op_proposal_set_status(id=pid, new_status="done", actor="builder")

    # Assertions
    state = op_state()
    assert state["status_counts"].get("done") == 1
    p = op_proposal_read(id=pid, status=None)[0]
    assert p["status"] == "done"
    assert p["version"] == 1
    assert p["retry_count"] == 0
    msgs = op_inbox_read(role=None, unacked_only=False, since=None, proposal=pid)
    # We expect at least: scan-result, 2 reviews, status→🟡 ack, status→🟢 ack,
    # status→⚙️ ack, handoff, codex return, verification review, status→✅ ack.
    assert len(msgs) >= 9
    kinds = [m["kind"] for m in msgs]
    assert "scan-result" in kinds
    assert kinds.count("review") >= 3
    assert "note" in kinds


def test_full_cycle_with_retry(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))

    pid = op_proposal_create(
        title="x", kind="refactor", executor="builder",
        effort="S", risk="S", risk_note=".", body=SAMPLE_BODY,
    )
    op_inbox_append(from_="builder", to="planner", kind="review", body="ok",
                    proposal=pid, re=None,
                    verdict="approved-for-human", for_version=1)
    op_inbox_append(from_="planner", to="builder", kind="review", body="ok",
                    proposal=pid, re=None,
                    verdict="approved-for-human", for_version=1)
    op_proposal_set_status(id=pid, new_status="awaiting-jonathan", actor="planner")
    op_proposal_set_status(id=pid, new_status="approved", actor="human")
    op_proposal_set_status(id=pid, new_status="in-progress", actor="builder")
    # Retry once
    op_proposal_set_status(id=pid, new_status="approved", actor="builder",
                           reason="flaky test")
    op_proposal_set_status(id=pid, new_status="in-progress", actor="builder")
    # Retry twice
    op_proposal_set_status(id=pid, new_status="approved", actor="builder",
                           reason="another flake")
    op_proposal_set_status(id=pid, new_status="in-progress", actor="builder")
    p = op_proposal_read(id=pid, status=None)[0]
    assert p["retry_count"] == 0  # reset on fresh 🟢 → ⚙️ each time
