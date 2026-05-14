"""Conductor v1 adapter — single-file CLI.

See Conductor Design §8.1 for the operation surface.
"""
from __future__ import annotations

import argparse
import re as _re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone as _tz
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


_PROP_HEADER_RE = _re.compile(r"^##\s+(?P<id>P-\d{3,})\s+—\s+(?P<title>.+)\s*$")
_STATUS_LINE_RE = _re.compile(
    r"^-\s+\*\*Status:\*\*\s+(?P<emoji>\S+)\s+(?P<rest>.+?)\s*$"
)
_PAUSED_STATUS_RE = _re.compile(
    r"^paused\s+\(from:\s+(?P<from_emoji>\S+)\s+(?P<from_rest>.+?)\)\s*$"
)
_FIELD_LINE_RE = _re.compile(r"^-\s+\*\*(?P<key>[^*]+?):\*\*\s+(?P<value>.+?)\s*$")
_EFFORT_RISK_RE = _re.compile(
    r"^-\s+\*\*Effort:\*\*\s+(?P<effort>[SML])\s+\|\s+\*\*Risk:\*\*\s+(?P<risk>[SML])\s*$"
)


def _split_proposal_blocks(text: str) -> list[list[str]]:
    """Split the Proposals file into one list-of-lines per proposal."""
    lines = text.splitlines()
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in lines:
        if _PROP_HEADER_RE.match(line):
            if current is not None:
                blocks.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
    if current is not None:
        blocks.append(current)
    return blocks


def _parse_section(lines: list[str], heading: str) -> list[str]:
    """Return the bullet/lines inside `### heading` until the next `### `."""
    out: list[str] = []
    in_section = False
    for line in lines:
        if line.strip() == f"### {heading}":
            in_section = True
            continue
        if in_section and line.startswith("### "):
            break
        if in_section:
            out.append(line)
    return [ln.strip() for ln in out if ln.strip()]


def parse_proposals(text: str) -> list[Proposal]:
    blocks = _split_proposal_blocks(text)
    proposals: list[Proposal] = []
    for block in blocks:
        hdr = _PROP_HEADER_RE.match(block[0])
        if not hdr:
            continue
        # Field lines come right after the header until the first blank or `### `.
        fields: dict[str, str] = {}
        status: Status | None = None
        status_paused_from: Status | None = None
        effort = risk = ""
        for line in block[1:]:
            if line.startswith("### ") or not line.strip():
                break
            sm = _STATUS_LINE_RE.match(line)
            if sm:
                emoji = sm.group("emoji")
                rest = sm.group("rest").strip()
                pm = _PAUSED_STATUS_RE.match(rest)
                if pm:
                    status = Status.PAUSED
                    status_paused_from = Status.from_emoji(pm.group("from_emoji"))
                else:
                    status = Status.from_emoji(emoji)
                continue
            em = _EFFORT_RISK_RE.match(line)
            if em:
                effort = em.group("effort")
                risk = em.group("risk")
                continue
            fm = _FIELD_LINE_RE.match(line)
            if fm:
                fields[fm.group("key").strip().lower()] = fm.group("value").strip()
        if status is None:
            continue
        summary_lines = _parse_section(block, "Summary")
        motivation_lines = _parse_section(block, "Motivation")
        scope = [ln.lstrip("- ").strip() for ln in _parse_section(block, "Scope")]
        acceptance = [ln.lstrip("- ").strip() for ln in _parse_section(block, "Acceptance")]
        evidence = [ln.lstrip("- ").strip() for ln in _parse_section(block, "Evidence")]
        linked_raw = _parse_section(block, "Linked Messages")
        linked = [m.strip() for m in ",".join(linked_raw).split(",") if m.strip()]
        delegated_to_str = fields.get("delegated to")
        delegated_paths_str = fields.get("delegated paths", "")
        delegated_paths = [
            p.strip(" `") for p in delegated_paths_str.split(",") if p.strip()
        ]
        proposals.append(
            Proposal(
                id=hdr.group("id"),
                title=hdr.group("title").strip(),
                kind=fields["kind"],
                version=int(fields["version"]),
                executor=Role(fields["executor"]),
                status=status,
                status_paused_from=status_paused_from,
                retry_count=int(fields.get("retry count", "0")),
                delegated_to=Role(delegated_to_str) if delegated_to_str else None,
                delegated_paths=delegated_paths,
                summary=" ".join(summary_lines),
                motivation=" ".join(motivation_lines),
                scope=scope,
                acceptance=acceptance,
                evidence=evidence,
                effort=effort,
                risk=risk,
                risk_note=fields.get("risk note", ""),
                linked_messages=linked,
            )
        )
    return proposals


def format_proposal(prop: Proposal) -> str:
    """Render a Proposal per the §5.3 normative form."""
    if prop.status is Status.PAUSED:
        assert prop.status_paused_from is not None
        sp = prop.status_paused_from
        status_line = f"- **Status:** ⏸️ paused (from: {sp.emoji} {sp.slug})"
    else:
        status_line = f"- **Status:** {prop.status.emoji} {prop.status.slug}"
    lines = [
        f"## {prop.id} — {prop.title}",
        status_line,
        f"- **Kind:** {prop.kind}",
        f"- **Version:** {prop.version}",
        f"- **Executor:** {prop.executor.value}",
    ]
    if prop.delegated_to is not None:
        lines.append(f"- **Delegated to:** {prop.delegated_to.value}")
        paths = ", ".join(f"`{p}`" for p in prop.delegated_paths)
        lines.append(f"- **Delegated paths:** {paths}")
    lines += [
        f"- **Effort:** {prop.effort} | **Risk:** {prop.risk}",
        f"- **Risk note:** {prop.risk_note}",
        f"- **Retry count:** {prop.retry_count}",
        "",
        "### Summary",
        prop.summary,
        "",
        "### Motivation",
        prop.motivation,
        "",
        "### Scope",
        *(f"- {s}" for s in prop.scope),
        "",
        "### Acceptance",
        *(f"- {a}" for a in prop.acceptance),
        "",
        "### Evidence",
        *(f"- {e}" for e in prop.evidence),
        "",
        "### Linked Messages",
        ", ".join(prop.linked_messages) if prop.linked_messages else "",
    ]
    return "\n".join(lines) + "\n"


import fcntl
import os as _os
from contextlib import contextmanager
from pathlib import Path as _Path


def _conductor_dir() -> _Path:
    val = _os.environ.get("CONDUCTOR_DIR")
    if not val:
        raise RuntimeError("CONDUCTOR_DIR is not set")
    return _Path(val)


@contextmanager
def _flock(lockfile: _Path):
    """Exclusive blocking flock context manager."""
    fd = _os.open(str(lockfile), _os.O_RDWR | _os.O_CREAT)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            _os.close(fd)


@contextmanager
def inbox_lock():
    """Exclusive lock on the Inbox file."""
    with _flock(_conductor_dir() / ".conductor" / "inbox.lock"):
        yield


@contextmanager
def proposals_lock():
    """Exclusive lock on the Proposals file."""
    with _flock(_conductor_dir() / ".conductor" / "proposals.lock"):
        yield


@contextmanager
def supermutation():
    """Two-lock supermutation: proposals.lock → inbox.lock, fixed order (§8.1)."""
    with proposals_lock():
        with inbox_lock():
            yield


def _inbox_path() -> _Path:
    return _conductor_dir() / "Conductor Inbox.md"


def _proposals_path() -> _Path:
    return _conductor_dir() / "Conductor Proposals.md"


def _read_inbox_text() -> str:
    p = _inbox_path()
    return p.read_text() if p.exists() else "# Conductor Inbox\n"


def _next_message_id(text: str) -> str:
    msgs = parse_inbox(text)
    n = max((int(m.id.split("-")[1]) for m in msgs), default=0) + 1
    return f"M-{n:04d}"


def _now_utc() -> datetime:
    return datetime.now(tz=_tz.utc).replace(microsecond=0)


def op_inbox_append(
    *,
    from_: str,
    to: str,
    kind: str,
    body: str,
    proposal: str | None,
    re: str | None,
    verdict: str | None,
    for_version: int | None,
) -> str:
    """Append a message; return its new M-NNNN id."""
    with inbox_lock():
        text = _read_inbox_text()
        new_id = _next_message_id(text)
        msg = Message(
            id=new_id,
            from_=Role(from_),
            to=Role(to),
            ts=_now_utc(),
            kind=Kind(kind),
            verdict=Verdict(verdict) if verdict else None,
            for_version=for_version,
            re=re,
            proposal=proposal,
            body=body,
        )
        rendered = format_message(msg)
        with open(_inbox_path(), "a") as fh:
            fh.write(rendered)
        return new_id


def op_inbox_read(
    *,
    role: str | None,
    unacked_only: bool,
    since: str | None,
    proposal: str | None,
) -> list[dict]:
    """Return messages as a list of dicts. Filters apply in order:
    role (`to` matches, or `to=both`), since (id > since), proposal."""
    with inbox_lock():
        msgs = parse_inbox(_read_inbox_text())

    role_enum = Role(role) if role else None

    def _matches(m: Message) -> bool:
        if role_enum is not None and m.to != role_enum and m.to != Role.BOTH:
            return False
        if since is not None and m.id <= since:
            return False
        if proposal is not None and m.proposal != proposal:
            return False
        return True

    filtered = [m for m in msgs if _matches(m)]

    if unacked_only and role_enum is not None:
        # An ack: kind=ack, from=role, re=<original id>
        acked_ids = {
            m.re for m in msgs
            if m.kind is Kind.ACK and m.from_ == role_enum and m.re
        }
        filtered = [m for m in filtered if m.id not in acked_ids]

    return [
        {
            "id": m.id,
            "from": m.from_.value,
            "to": m.to.value,
            "ts": m.ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "kind": m.kind.value,
            "verdict": m.verdict.value if m.verdict else None,
            "for_version": m.for_version,
            "re": m.re,
            "proposal": m.proposal,
            "body": m.body,
        }
        for m in filtered
    ]


def op_inbox_ack(*, message_id: str, by: str) -> str:
    """Append a `kind: ack` message; idempotent — if an ack from `by` for
    `message_id` already exists, return its id without writing."""
    by_role = Role(by)
    with inbox_lock():
        text = _read_inbox_text()
        msgs = parse_inbox(text)
        for m in msgs:
            if (
                m.kind is Kind.ACK
                and m.re == message_id
                and m.from_ == by_role
            ):
                return m.id
        # Recipient of the ack: the original message's sender, or `both`.
        target = Role.BOTH
        for m in msgs:
            if m.id == message_id:
                target = m.from_
                break
        new_id = _next_message_id(text)
        ts = _now_utc()
        ack = Message(
            id=new_id,
            from_=by_role,
            to=target,
            ts=ts,
            kind=Kind.ACK,
            re=message_id,
            body=f"ack: {message_id} by {by} @ {ts.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        )
        with open(_inbox_path(), "a") as fh:
            fh.write(format_message(ack))
        return new_id


REQUIRED_PROPOSAL_SECTIONS = ("Summary", "Motivation", "Scope", "Acceptance", "Evidence")


def _parse_proposal_body(body: str) -> dict[str, object]:
    """Extract Summary/Motivation/Scope/Acceptance/Evidence from `### ...` sections."""
    text = "# Conductor Proposals\n\n## P-XXX — placeholder\n- **Status:** 🔵 drafting\n" \
           "- **Kind:** feature\n- **Version:** 1\n- **Executor:** builder\n" \
           "- **Effort:** S | **Risk:** S\n- **Risk note:** _\n- **Retry count:** 0\n\n" \
           + body
    fake_lines = text.splitlines()
    sections = {
        name: _parse_section(fake_lines, name) for name in REQUIRED_PROPOSAL_SECTIONS
    }
    missing = [n for n in REQUIRED_PROPOSAL_SECTIONS if not sections[n]]
    if missing:
        raise ValueError(f"missing required section(s) in body: {missing}")
    return {
        "summary": " ".join(sections["Summary"]),
        "motivation": " ".join(sections["Motivation"]),
        "scope": [ln.lstrip("- ").strip() for ln in sections["Scope"]],
        "acceptance": [ln.lstrip("- ").strip() for ln in sections["Acceptance"]],
        "evidence": [ln.lstrip("- ").strip() for ln in sections["Evidence"]],
    }


def _read_proposals_text() -> str:
    p = _proposals_path()
    return p.read_text() if p.exists() else "# Conductor Proposals\n"


def _next_proposal_id(text: str) -> str:
    props = parse_proposals(text)
    n = max((int(p.id.split("-")[1]) for p in props), default=0) + 1
    return f"P-{n:03d}"


def op_proposal_create(
    *,
    title: str,
    kind: str,
    executor: str,
    effort: str,
    risk: str,
    risk_note: str,
    body: str,
) -> str:
    """Create a new proposal at version=1, status=🔵 drafting, retry_count=0."""
    parsed = _parse_proposal_body(body)
    with proposals_lock():
        text = _read_proposals_text()
        new_id = _next_proposal_id(text)
        prop = Proposal(
            id=new_id,
            title=title,
            kind=kind,
            version=1,
            executor=Role(executor),
            status=Status.DRAFTING,
            retry_count=0,
            summary=parsed["summary"],
            motivation=parsed["motivation"],
            scope=parsed["scope"],
            acceptance=parsed["acceptance"],
            evidence=parsed["evidence"],
            effort=effort,
            risk=risk,
            risk_note=risk_note,
            linked_messages=[],
        )
        rendered = format_proposal(prop)
        with open(_proposals_path(), "a") as fh:
            fh.write("\n" + rendered)
        return new_id


def op_proposal_read(*, id: str | None, status: str | None) -> list[dict]:
    with proposals_lock():
        props = parse_proposals(_read_proposals_text())

    def _matches(p: Proposal) -> bool:
        if id is not None and p.id != id:
            return False
        if status is not None and p.status.slug != status and p.status.emoji != status:
            return False
        return True

    return [
        {
            "id": p.id,
            "title": p.title,
            "kind": p.kind,
            "version": p.version,
            "executor": p.executor.value,
            "delegated_to": p.delegated_to.value if p.delegated_to else None,
            "delegated_paths": list(p.delegated_paths),
            "status": p.status.slug,
            "status_paused_from": p.status_paused_from.slug if p.status_paused_from else None,
            "retry_count": p.retry_count,
            "effort": p.effort,
            "risk": p.risk,
            "risk_note": p.risk_note,
            "summary": p.summary,
            "motivation": p.motivation,
            "scope": list(p.scope),
            "acceptance": list(p.acceptance),
            "evidence": list(p.evidence),
            "linked_messages": list(p.linked_messages),
        }
        for p in props if _matches(p)
    ]


class FSMError(ValueError):
    """Raised when a status transition is not permitted."""


# Mapping of (from_status, to_status) → set of allowed actors.
# Resume (⏸️ → prior) is handled separately because it requires the proposal's
# `status_paused_from` field; not encoded here.
FSM_TRANSITIONS: dict[tuple[Status, Status], set[Role]] = {
    (Status.DRAFTING, Status.AWAITING_JONATHAN): {Role.PLANNER, Role.BUILDER},
    (Status.AWAITING_JONATHAN, Status.APPROVED): {Role.HUMAN},
    (Status.AWAITING_JONATHAN, Status.REJECTED): {Role.HUMAN},
    (Status.AWAITING_JONATHAN, Status.DRAFTING): {Role.HUMAN},
    (Status.APPROVED, Status.DRAFTING): {Role.HUMAN},
    (Status.APPROVED, Status.IN_PROGRESS): {Role.BUILDER},
    (Status.APPROVED, Status.DONE): {Role.PLANNER},
    (Status.IN_PROGRESS, Status.DONE): {Role.BUILDER},
    (Status.IN_PROGRESS, Status.APPROVED): {Role.BUILDER},        # retry
    (Status.IN_PROGRESS, Status.AWAITING_JONATHAN): {Role.BUILDER},  # escalate
    (Status.IN_PROGRESS, Status.REJECTED): {Role.BUILDER, Role.HUMAN},
    (Status.DRAFTING, Status.REJECTED): {Role.BUILDER, Role.HUMAN},
}

# Any non-terminal state may pause.
_PAUSABLE = {
    Status.DRAFTING, Status.AWAITING_JONATHAN, Status.APPROVED, Status.IN_PROGRESS
}


def validate_transition(
    from_status: Status, to_status: Status, actor: Role
) -> None:
    """Raise FSMError if the (from, to, actor) transition is not permitted."""
    if to_status is Status.PAUSED:
        if from_status not in _PAUSABLE:
            raise FSMError(
                f"cannot pause from terminal/paused state {from_status.slug}: invalid transition"
            )
        if actor not in {Role.PLANNER, Role.BUILDER, Role.HUMAN}:
            raise FSMError(f"actor {actor.value} cannot pause")
        return
    allowed = FSM_TRANSITIONS.get((from_status, to_status))
    if allowed is None:
        raise FSMError(
            f"transition {from_status.slug} → {to_status.slug} is not permitted"
        )
    if actor not in allowed:
        raise FSMError(
            f"actor {actor.value} cannot make transition "
            f"{from_status.slug} → {to_status.slug}; allowed: "
            f"{sorted(a.value for a in allowed)}"
        )


def _resolve_status(name: str) -> Status:
    """Accept either a status slug ('approved') or emoji ('🟢') and return the Status enum."""
    for s in Status:
        if name == s.slug or name == s.emoji:
            return s
    raise StatusError(f"unknown status: {name!r}")


def _write_proposals_text(text: str) -> None:
    """Atomically replace the Proposals file with `text` (temp-file + rename)."""
    target = _proposals_path()
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(text)
    _os.rename(str(tmp), str(target))


def _serialize_proposals(props: list[Proposal]) -> str:
    """Re-emit the entire Proposals file from a list (preserves header)."""
    header = "# Conductor Proposals\n\nFSM-controlled ledger. See [[Conductor Design]] §5.\n"
    if not props:
        return header + "\n*No proposals yet.*\n"
    parts = [header]
    for p in props:
        parts.append("\n" + format_proposal(p))
    return "".join(parts)


def op_proposal_set_status(
    *,
    id: str,
    new_status: str,
    actor: str,
    reason: str | None = None,
    executor: str | None = None,
    delegated_to: str | None = None,
    delegated_paths: list[str] | None = None,
) -> str:
    """Set a proposal's status. Atomically writes both Proposals and an ack to Inbox
    under a two-lock supermutation. Returns 'noop' on same-state writes, else 'ok'."""
    target_status = _resolve_status(new_status)
    actor_role = Role(actor)
    with supermutation():
        props = parse_proposals(_read_proposals_text())
        for idx, p in enumerate(props):
            if p.id == id:
                break
        else:
            raise ValueError(f"proposal {id} not found")
        from_status = p.status

        # Idempotency
        if from_status is target_status:
            return "noop"

        # Resume handling
        if from_status is Status.PAUSED:
            if target_status is not p.status_paused_from:
                raise FSMError(
                    f"⏸️ can only resume to {p.status_paused_from.slug if p.status_paused_from else '?'} "
                    f"— refusing to resume to {target_status.slug}"
                )
            resume_from = p.status_paused_from
            if resume_from is None:
                raise FSMError("paused proposal has no status_paused_from recorded")
            # The "actor" for resume is anyone allowed at the from_status's outbound set.
            # Simplest: allow planner/builder/human (any of the three).
            if actor_role not in {Role.PLANNER, Role.BUILDER, Role.HUMAN}:
                raise FSMError(f"actor {actor_role.value} cannot resume")
            p.status = resume_from
            p.status_paused_from = None
        else:
            # Pause → check pausable
            if target_status is Status.PAUSED:
                validate_transition(from_status, target_status, actor_role)
                p.status_paused_from = from_status
                p.status = Status.PAUSED
            else:
                # Standard transition
                validate_transition(from_status, target_status, actor_role)

                # Retry cap: 🟢 → ⚙️ resets per-execution counter to 0 (fresh attempt);
                # ⚙️ → 🟢 increments per-execution counter AND checks cumulative inbox cap.
                # Cap: the proposal may have at most 2 prior "in-progress → approved"
                # transitions recorded in the inbox before a third is rejected.
                if from_status is Status.IN_PROGRESS and target_status is Status.APPROVED:
                    # Count cumulative retries via inbox ack notes for this proposal.
                    prior_retries = sum(
                        1 for m in parse_inbox(_read_inbox_text())
                        if m.proposal == id
                        and m.kind is Kind.NOTE
                        and "in-progress → approved" in m.body
                    )
                    if prior_retries >= 2:
                        raise FSMError(
                            f"retry cap reached ({prior_retries} retries recorded); "
                            f"escalate via ⚙️ → 🟡 instead"
                        )
                    p.retry_count += 1
                elif from_status is Status.APPROVED and target_status is Status.IN_PROGRESS:
                    p.retry_count = 0
                p.status = target_status

        # Atomic approval optional fields
        if target_status is Status.APPROVED and from_status is Status.AWAITING_JONATHAN:
            if executor is not None:
                p.executor = Role(executor)
            if delegated_to is not None:
                p.delegated_to = Role(delegated_to)
                p.delegated_paths = list(delegated_paths or [])
                # Adapter-side path validation (§5.1)
                bad = [
                    path for path in p.delegated_paths
                    if not path.startswith(("Projects/", "Concepts/", "Papers/", "Personal/"))
                ]
                if bad:
                    raise ValueError(f"delegated_paths contain disallowed prefixes: {bad}")

        # Write proposals atomically
        props[idx] = p
        _write_proposals_text(_serialize_proposals(props))

        # Emit ack to Inbox under the same supermutation
        text = _read_inbox_text()
        new_id = _next_message_id(text)
        rsn = f"  (reason: {reason})" if reason else ""
        ack = Message(
            id=new_id,
            from_=actor_role,
            to=Role.BOTH,
            ts=_now_utc(),
            kind=Kind.NOTE,
            proposal=id,
            body=f"status: {from_status.slug} → {p.status.slug} by {actor}{rsn}",
        )
        with open(_inbox_path(), "a") as fh:
            fh.write(format_message(ack))

    return "ok"


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
