# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

The v1 file-backed adapter for Conductor — a single-file Python CLI
(`conductor.py`) that exposes the operation surface used by the Planner
and Builder Claude Code sessions. Both sessions invoke it via Bash. In v2,
the same op surface will be re-exposed as an MCP server; kebab-case op names
(`inbox-append`) map mechanically to snake_case tool names (`inbox_append`)
with arguments and return shapes preserved 1:1 — keep that invariant in mind
when changing argparse names or return JSON.

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

`conductor.py` is intentionally one file with four layered concerns:

1. **Domain types** — `Role`, `Kind`, `Verdict`, `Status` enums and the
   `Message` / `Proposal` dataclasses. `Status` carries both a slug and an
   emoji; the on-disk format uses emoji, the JSON API uses slug.
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
   add a `main()` branch.

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

## v1 → v2 invariants

When editing op signatures, return shapes, or status/role/kind vocabulary,
remember v2 will re-export the same surface as MCP tools. Don't drift the
shapes casually — they're the v2 invariant. The Codex handoff template
is downstream of this adapter and **not** part of the invariant.
