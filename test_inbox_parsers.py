from datetime import datetime, timezone

from conductor import (
    Kind, Role, Verdict,
    Message,
    format_message, parse_inbox,
)


SAMPLE = """# Conductor Inbox

Append-only message log.

## M-0001 [from: human → both] 2026-05-14T12:00:00Z
[kind: note]

Bus initialized.

## M-0002 [from: planner → builder] 2026-05-14T12:05:00Z
[kind: scan-result] [proposal: P-001]

Found 3 candidates.

## M-0003 [from: builder → planner] 2026-05-14T12:10:00Z
[kind: review] [verdict: approved-for-human] [for_version: 1] [re: M-0002] [proposal: P-001]

Confirmed scope.
"""


def test_parse_inbox_returns_three_messages():
    msgs = parse_inbox(SAMPLE)
    assert len(msgs) == 3


def test_parse_inbox_first_message_fields():
    msgs = parse_inbox(SAMPLE)
    m1 = msgs[0]
    assert m1.id == "M-0001"
    assert m1.from_ is Role.HUMAN
    assert m1.to is Role.BOTH
    assert m1.ts == datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)
    assert m1.kind is Kind.NOTE
    assert m1.body.strip() == "Bus initialized."
    assert m1.verdict is None


def test_parse_inbox_third_message_review_fields():
    msgs = parse_inbox(SAMPLE)
    m3 = msgs[2]
    assert m3.kind is Kind.REVIEW
    assert m3.verdict is Verdict.APPROVED_FOR_HUMAN
    assert m3.for_version == 1
    assert m3.in_reply_to == "M-0002"
    assert m3.proposal == "P-001"


def test_format_message_roundtrip():
    msgs = parse_inbox(SAMPLE)
    for m in msgs:
        rendered = format_message(m)
        re_parsed = parse_inbox("# Conductor Inbox\n\n" + rendered)
        assert len(re_parsed) == 1
        rt = re_parsed[0]
        assert rt.id == m.id
        assert rt.from_ == m.from_
        assert rt.to == m.to
        assert rt.kind == m.kind
        assert rt.verdict == m.verdict
        assert rt.for_version == m.for_version
        assert rt.in_reply_to == m.in_reply_to
        assert rt.proposal == m.proposal
        assert rt.body.strip() == m.body.strip()


def test_format_message_tag_order():
    msg = Message(
        id="M-0042",
        from_=Role.BUILDER,
        to=Role.PLANNER,
        ts=datetime(2026, 5, 13, 14, 23, 11, tzinfo=timezone.utc),
        kind=Kind.REVIEW,
        verdict=Verdict.NEEDS_CHANGE,
        for_version=1,
        in_reply_to="M-0041",
        proposal="P-007",
        body="...",
    )
    rendered = format_message(msg)
    tag_line = rendered.splitlines()[1]
    # tags must appear in fixed order: kind, verdict, for_version, re, proposal
    assert tag_line.index("kind:") < tag_line.index("verdict:")
    assert tag_line.index("verdict:") < tag_line.index("for_version:")
    assert tag_line.index("for_version:") < tag_line.index("re:")
    assert tag_line.index("re:") < tag_line.index("proposal:")
