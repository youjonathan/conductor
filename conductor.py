"""Conductor v1 adapter — single-file CLI.

See Conductor Design §8.1 for the operation surface.
"""
from __future__ import annotations

import argparse
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
