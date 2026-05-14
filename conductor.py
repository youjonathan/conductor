"""Conductor v1 adapter — single-file CLI.

See Conductor Design §8.1 for the operation surface.
"""
from __future__ import annotations

import argparse
import re as _re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class StatusError(ValueError):
    """Raised on bad Status emoji or transitions."""


class Role(str, Enum):
    PLANNER = "planner"
    BUILDER = "builder"
    HUMAN = "human"
    CODEX = "codex"
    BOTH = "both"


class Kind(str, Enum):
    SCAN_REQUEST = "scan-request"
    SCAN_RESULT = "scan-result"
    PROPOSAL_DRAFT = "proposal-draft"
    REVIEW = "review"
    QUESTION = "question"
    NOTE = "note"
    ACK = "ack"


class Verdict(str, Enum):
    APPROVED_FOR_HUMAN = "approved-for-human"
    NEEDS_CHANGE = "needs-change"
    UNCLEAR = "unclear"


class Status(Enum):
    DRAFTING = ("drafting", "🔵")
    AWAITING_JONATHAN = ("awaiting-jonathan", "🟡")
    APPROVED = ("approved", "🟢")
    IN_PROGRESS = ("in-progress", "⚙️")
    DONE = ("done", "✅")
    REJECTED = ("rejected", "❌")
    PAUSED = ("paused", "⏸️")

    def __init__(self, slug: str, emoji: str) -> None:
        self.slug = slug
        self.emoji = emoji

    @classmethod
    def from_emoji(cls, emoji: str) -> "Status":
        for s in cls:
            if s.emoji == emoji:
                return s
        raise StatusError(f"unknown status emoji: {emoji!r}")


@dataclass
class Message:
    id: str
    from_: Role
    to: Role
    ts: datetime
    kind: Kind
    body: str
    re: Optional[str] = None
    proposal: Optional[str] = None
    verdict: Optional[Verdict] = None
    for_version: Optional[int] = None

    def __post_init__(self) -> None:
        if self.kind is Kind.REVIEW and self.proposal is not None:
            if self.verdict is None:
                raise ValueError(
                    "verdict is required when kind=review and proposal is set"
                )


@dataclass
class Proposal:
    id: str
    title: str
    kind: str  # "feature" | "drift" | "refactor" | "idea"
    version: int
    executor: Role
    status: Status
    summary: str
    motivation: str
    scope: list[str]
    acceptance: list[str]
    evidence: list[str]
    effort: str  # "S" | "M" | "L"
    risk: str
    risk_note: str
    linked_messages: list[str]
    retry_count: int = 0
    delegated_to: Optional[Role] = None
    delegated_paths: list[str] = field(default_factory=list)
    status_paused_from: Optional[Status] = None


OPERATIONS = [
    "inbox-append",
    "inbox-read",
    "inbox-ack",
    "proposal-create",
    "proposal-read",
    "proposal-edit-body",
    "proposal-set-status",
    "state",
]


_HEADER_RE = _re.compile(
    r"^##\s+(?P<id>M-\d{4})\s+"
    r"\[from:\s*(?P<from>\w+)\s*→\s*(?P<to>\w+)\]\s+"
    r"(?P<ts>\S+)\s*$"
)


def _parse_tag_line(line: str) -> dict[str, str]:
    """Parse `[kind: review] [verdict: ...] ...` into a dict."""
    tags: dict[str, str] = {}
    for match in _re.finditer(r"\[(?P<k>[a-z_]+):\s*(?P<v>[^\]]+?)\s*\]", line):
        tags[match.group("k")] = match.group("v")
    return tags


def parse_inbox(text: str) -> list[Message]:
    """Parse the Inbox markdown text into a list of Messages, in file order."""
    lines = text.splitlines()
    messages: list[Message] = []
    i = 0
    while i < len(lines):
        m = _HEADER_RE.match(lines[i])
        if not m:
            i += 1
            continue
        if i + 1 >= len(lines):
            break
        tag_line = lines[i + 1]
        tags = _parse_tag_line(tag_line)
        # body runs until the next `## M-` header or EOF
        body_start = i + 2
        body_end = body_start
        while body_end < len(lines) and not _HEADER_RE.match(lines[body_end]):
            body_end += 1
        body = "\n".join(lines[body_start:body_end]).strip()
        ts = datetime.fromisoformat(m.group("ts").replace("Z", "+00:00"))
        verdict_str = tags.get("verdict")
        for_version_str = tags.get("for_version")
        messages.append(
            Message(
                id=m.group("id"),
                from_=Role(m.group("from")),
                to=Role(m.group("to")),
                ts=ts,
                kind=Kind(tags["kind"]),
                verdict=Verdict(verdict_str) if verdict_str else None,
                for_version=int(for_version_str) if for_version_str else None,
                re=tags.get("re"),
                proposal=tags.get("proposal"),
                body=body,
            )
        )
        i = body_end
    return messages


def format_message(msg: Message) -> str:
    """Render a Message as the §4.3 markdown form."""
    ts = msg.ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    header = (
        f"## {msg.id} [from: {msg.from_.value} → {msg.to.value}] {ts}"
    )
    tags = [f"[kind: {msg.kind.value}]"]
    if msg.verdict is not None:
        tags.append(f"[verdict: {msg.verdict.value}]")
    if msg.for_version is not None:
        tags.append(f"[for_version: {msg.for_version}]")
    if msg.re is not None:
        tags.append(f"[re: {msg.re}]")
    if msg.proposal is not None:
        tags.append(f"[proposal: {msg.proposal}]")
    tag_line = " ".join(tags)
    return f"{header}\n{tag_line}\n\n{msg.body}\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="conductor",
        description="Conductor v1 adapter — see Conductor Design §8.1.",
    )
    subparsers = parser.add_subparsers(dest="op", required=False)
    for op in OPERATIONS:
        subparsers.add_parser(op, help=f"{op} operation (see §8.1)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.op is None:
        parser.print_help()
        return 0
    print(f"NotImplementedError: {args.op}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
