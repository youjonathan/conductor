from conductor import (
    Role, Status,
    Proposal,
    format_proposal, parse_proposals,
)


SAMPLE = """# Conductor Proposals

FSM-controlled ledger. See [[Conductor Design]] §5.

## P-007 — Remove dead `RetrieverV1` import shim
- **Status:** 🟡 awaiting-jonathan
- **Kind:** refactor
- **Version:** 1
- **Executor:** builder
- **Effort:** S | **Risk:** S
- **Risk note:** purely additive deletion; covered by existing tests.
- **Retry count:** 0

### Summary
S1.
S2.

### Motivation
M1.

### Scope
- `vhile/retrieval/__init__.py`
- `tests/test_imports.py`

### Acceptance
- `vhile/retrieval/__init__.py` no longer references `RetrieverV1`.
- `pytest tests/ -q` is green.

### Evidence
- `vhile/retrieval/__init__.py:23-29`.

### Linked Messages
M-0040, M-0041, M-0042
"""


def test_parse_proposals_returns_one():
    props = parse_proposals(SAMPLE)
    assert len(props) == 1


def test_parse_proposal_fields():
    p = parse_proposals(SAMPLE)[0]
    assert p.id == "P-007"
    assert p.title == "Remove dead `RetrieverV1` import shim"
    assert p.status is Status.AWAITING_JONATHAN
    assert p.kind.value == "refactor"
    assert p.version == 1
    assert p.executor is Role.BUILDER
    assert p.effort == "S"
    assert p.risk == "S"
    assert p.risk_note == "purely additive deletion; covered by existing tests."
    assert p.retry_count == 0
    assert p.delegated_to is None
    assert p.delegated_paths == []
    assert p.scope == ["`vhile/retrieval/__init__.py`", "`tests/test_imports.py`"]
    assert p.linked_messages == ["M-0040", "M-0041", "M-0042"]


def test_format_proposal_roundtrip():
    p = parse_proposals(SAMPLE)[0]
    rendered = format_proposal(p)
    re_parsed = parse_proposals("# Conductor Proposals\n\n" + rendered)
    assert len(re_parsed) == 1
    rt = re_parsed[0]
    assert rt.id == p.id
    assert rt.title == p.title
    assert rt.status == p.status
    assert rt.version == p.version
    assert rt.retry_count == p.retry_count
    assert rt.scope == p.scope
    assert rt.linked_messages == p.linked_messages


def test_format_proposal_paused_status_line():
    p = parse_proposals(SAMPLE)[0]
    p.status = Status.PAUSED
    p.status_paused_from = Status.IN_PROGRESS
    rendered = format_proposal(p)
    assert "**Status:** ⏸️ paused (from: ⚙️ in-progress)" in rendered


def test_format_proposal_delegation_lines():
    p = parse_proposals(SAMPLE)[0]
    p.executor = Role.PLANNER
    p.delegated_to = Role.BUILDER
    p.delegated_paths = ["Projects/VHIL-E/VHIL-E System Design v2.md"]
    rendered = format_proposal(p)
    assert "**Executor:** planner" in rendered
    assert "**Delegated to:** builder" in rendered
    assert "**Delegated paths:** `Projects/VHIL-E/VHIL-E System Design v2.md`" in rendered
