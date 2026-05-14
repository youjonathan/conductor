# Conductor adapter

This is the v1 file-backed implementation of the Conductor adapter. It exposes
the operation surface defined in [Conductor Design §8.1](../Conductor%20Design.md)
as a CLI; both the Planner and Builder Claude Code sessions invoke it via Bash.

## Invocation

```bash
export CONDUCTOR_DIR="/path/to/Conductor"
python3 conductor.py <op> [--args...] [< body-on-stdin]
```

Operations:

| Op | Purpose |
|---|---|
| `inbox-append`        | Append a message to the bus. |
| `inbox-read`          | Read messages (filter by role/unacked/since/proposal). |
| `inbox-ack`           | Idempotently ack a message by id. |
| `proposal-create`     | Create a proposal (body via stdin, sections per §8.1). |
| `proposal-read`       | Read proposals (filter by id/status). |
| `proposal-edit-body`  | Edit a 🔵 drafting proposal's body; bumps `version`. |
| `proposal-set-status` | FSM-validated status transition; atomic with ack emit. |
| `state`               | Compact JSON summary of bus state. |

See `python3 conductor.py <op> --help` for each op's arguments.

## Locking

All write ops acquire `flock` on `.conductor/inbox.lock` or `.conductor/proposals.lock`.
Cross-file mutations (status transitions, body edits) acquire both in order:
`proposals.lock` → `inbox.lock`. The fixed order prevents deadlock.

## Tests

```bash
cd .conductor
pytest -v
```

## v1 → v2 swap

In v2, this CLI is replaced by an MCP server that exposes the same operations
as tools. Per Conductor Design §12, the name translation is mechanical: every
kebab-case op name (`inbox-append`) maps to a snake_case MCP tool name
(`inbox_append`), with arguments and return shapes preserved 1:1. Role
prompts do not change between v1 and v2.

The Codex handoff template (Design §7.2) is downstream of Conductor and not
part of the v1→v2 invariant — it reflects the local filesystem, git/GitHub,
and the `codex:rescue` skill's contract.
