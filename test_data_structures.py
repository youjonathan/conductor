from datetime import datetime, timezone

from conductor import (
    Kind, Role, Status, Verdict, ProposalKind,
    Message, Proposal,
    StatusError,
)


def test_role_enum_values():
    assert {r.value for r in Role} == {
        "planner", "builder", "human", "codex", "both",
    }


def test_kind_enum_values():
    assert {k.value for k in Kind} == {
        "scan-request", "scan-result", "proposal-draft",
        "review", "question", "note", "ack",
    }


def test_verdict_enum_values():
    assert {v.value for v in Verdict} == {
        "approved-for-human", "needs-change", "unclear",
    }


def test_status_enum_emojis():
    assert Status.DRAFTING.emoji == "🔵"
    assert Status.AWAITING_JONATHAN.emoji == "🟡"
    assert Status.APPROVED.emoji == "🟢"
    assert Status.IN_PROGRESS.emoji == "⚙️"
    assert Status.DONE.emoji == "✅"
    assert Status.REJECTED.emoji == "❌"
    assert Status.PAUSED.emoji == "⏸️"


def test_status_from_emoji_roundtrip():
    for s in Status:
        assert Status.from_emoji(s.emoji) is s


def test_status_from_emoji_invalid():
    try:
        Status.from_emoji("🟣")
    except StatusError as exc:
        assert "🟣" in str(exc)
    else:
        raise AssertionError("expected StatusError")


def test_message_dataclass_minimal():
    msg = Message(
        id="M-0001",
        from_=Role.HUMAN,
        to=Role.BOTH,
        ts=datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc),
        kind=Kind.NOTE,
        body="bus initialized.",
    )
    assert msg.id == "M-0001"
    assert msg.verdict is None
    assert msg.for_version is None


def test_message_review_requires_verdict_when_proposal_set():
    try:
        Message(
            id="M-0002",
            from_=Role.PLANNER,
            to=Role.BUILDER,
            ts=datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc),
            kind=Kind.REVIEW,
            proposal="P-001",
            body="missing verdict",
        )
    except ValueError as exc:
        assert "verdict" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError")


def test_proposal_dataclass_defaults():
    prop = Proposal(
        id="P-001",
        title="Sample",
        kind=ProposalKind.REFACTOR,
        version=1,
        executor=Role.BUILDER,
        status=Status.DRAFTING,
        summary="s",
        motivation="m",
        scope=["a"],
        acceptance=["b"],
        evidence=["c"],
        effort="S",
        risk="S",
        risk_note="n",
        linked_messages=[],
    )
    assert prop.retry_count == 0
    assert prop.delegated_to is None
    assert prop.delegated_paths == []
    assert prop.status_paused_from is None
