# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

The file-backed adapter for Conductor. `conductor.py` owns the domain model,
markdown storage, locking, FSM, and CLI; `conductor_mcp.py` exposes the same
operation surface as a FastMCP server for agent harnesses. Kebab-case CLI ops
(`inbox-append`) map mechanically to snake_case MCP tool names
(`inbox_append`), with arguments and return shapes preserved 1:1.

## Commands

```bash
# Run the full test suite (from repo root)
pytest -v

# Run a single file or test
pytest -v test_fsm.py
pytest -v test_fsm.py::test_drafting_to_awaiting

# Invoke the CLI (CONDUCTOR_DIR must point at a vault root that contains
# `Conductor Inbox.md`, `Conductor Proposals.md`, and a `.conductor/` dir
# with `inbox.lock` + `proposals.lock`)
export CONDUCTOR_DIR=/path/to/vault
python3 conductor.py state
python3 conductor.py <op> --help
```

Tests stub `CONDUCTOR_DIR` via `tmp_path` + `monkeypatch` and seed the four
files above — see `test_e2e_smoke.py::_seed` for the canonical layout.

## Architecture

`conductor.py` is intentionally one file with five layered concerns:

1. **Domain types** — `Role`, `Kind`, `Verdict`, `ProposalKind`, `Status` enums
   and the `Message` / `Proposal` dataclasses.
2. **Parsers / formatters** — `parse_inbox` / `format_message` and
   `parse_proposals` / `format_proposal` are the only code that touches the
   markdown grammar. Header/tag/section regexes live next to them. Keep the
   round-trip (`parse → format → parse`) stable; tests rely on it.
3. **Locking** — `inbox_lock()`, `proposals_lock()`, and `supermutation()`
   are blocking `flock` context managers. **Cross-file mutations must use
   `supermutation()`**, which always acquires `proposals.lock` → `inbox.lock`
   in that fixed order to prevent deadlock. Don't introduce new lock-acquire
   sites that violate the order.
4. **Operations** — `op_*` functions are the public surface listed in
   `OPERATIONS`. Each maps 1:1 to an argparse subcommand wired in
   `build_parser()` and dispatched in `main()`. Adding an op means: write
   `op_foo`, add it to `OPERATIONS`, add a `subs.add_parser("foo")` block,
   add a `main()` branch — **and** add a matching `@mcp.tool` wrapper in
   `conductor_mcp.py` (see layer 5).
5. **MCP wrapper** — `conductor_mcp.py` is a thin FastMCP server. One
   `@mcp.tool` per `op_*`; kebab-case op names map to snake_case tool names
   (`inbox-append` → `inbox_append`). Args and return shapes pass through
   unchanged; FastMCP handles protocol wrapping. The `inbox_append` tool
   aliases its `from_` parameter to `from` via Pydantic so the MCP schema
   matches v1's CLI flag and JSON return key. `main()` validates the
   `CONDUCTOR_DIR` layout before `mcp.run()`; missing config exits with a
   stderr message and code 1.

### FSM (proposal status transitions)

`FSM_TRANSITIONS` is the single source of truth for `(from, to) → {allowed
actors}`. Pause/resume is **not** in that table — pausing is handled by the
`_PAUSABLE` set in `validate_transition`, and resume reads
`status_paused_from` off the proposal in `op_proposal_set_status`. If you
add a new status or actor, update both `FSM_TRANSITIONS` and the pause
logic.

Retry cap is enforced at `⚙️ → 🟢` (in-progress → approved): cumulative
prior retries are counted by scanning Inbox notes for this proposal whose
body contains `"in-progress → approved"`. The cap is 2; the 3rd triggers
`FSMError` and the caller is expected to escalate via `⚙️ → 🟡` instead.

### Atomicity guarantees the tests assert

- `proposal-set-status` writes the Proposals file **and** appends an audit
  note to the Inbox inside one `supermutation()`. Both succeed or neither
  does. Proposals is rewritten atomically via temp-file + rename
  (`_write_proposals_text`).
- `inbox-ack` is idempotent: if an ack from the same actor for the same
  message id already exists, it returns the existing id without writing.
- `proposal-edit-body` is only legal at `🔵 drafting`; it bumps `version`
  and emits a body-edit note to the Inbox under the same supermutation.

### Inbox semantics worth knowing

- `inbox-read --unacked --role X` self-filters: it never returns
  messages where `from == X`. This is so the `to: both` audit notes that
  supermutations emit don't show up in the originator's own unacked queue.
  `op_state` applies the same self-filter when computing per-role unacked
  counts.
- `inbox-ack` accepts both `--message-id`/`--by` (canonical) and
  `--id`/`--role` (shorthand). The aliases were added after both Planner
  and Builder reached for the short forms in cycle 1; treat them as
  permanent and additive.

### Path validation

Approving a proposal with `delegated_paths` validates each path against the
prefixes `Projects/`, `Concepts/`, `Papers/`, `Personal/`. Anything
else raises `ValueError`. This is enforced adapter-side, not by the FSM.

## Interface invariants

When editing op signatures, return shapes, or status/role/kind vocabulary,
keep the CLI and MCP surfaces aligned. Don't drift the shapes casually; the
Codex handoff template is downstream of this adapter and **not** part of the
interface invariant.
