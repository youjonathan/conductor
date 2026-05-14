# Conductor role prompts

The two system-prompt contracts for the Claude Code sessions in a Conductor
pair:

- [`planner.md`](./planner.md) — the **Planner**, working over a knowledge
  base (notes, PRDs, design docs, papers, ideas).
- [`builder.md`](./builder.md) — the **Builder**, working over a code repo.

Drop these into your Claude Code sessions as system prompts (or as the body
of a custom skill) and you have a working pair.

## What each session needs

**Both sessions** need `CONDUCTOR_DIR` pointed at a shared directory that
contains:

```
$CONDUCTOR_DIR/
├── Conductor Inbox.md         # append-only message log
├── Conductor Proposals.md     # FSM-controlled ledger
└── .conductor/
    ├── inbox.lock             # flock target
    └── proposals.lock         # flock target
```

Bootstrap empty:

```bash
mkdir -p "$CONDUCTOR_DIR/.conductor"
: > "$CONDUCTOR_DIR/.conductor/inbox.lock"
: > "$CONDUCTOR_DIR/.conductor/proposals.lock"
echo "# Conductor Inbox"     > "$CONDUCTOR_DIR/Conductor Inbox.md"
echo "# Conductor Proposals" > "$CONDUCTOR_DIR/Conductor Proposals.md"
```

Both sessions also need the `conductor` CLI on `PATH` (from this repo's
`pip install .`).

**Planner** runs from the knowledge-base root. Its `cwd` is wherever your
notes live.

**Builder** additionally needs:

- `REPO_DIR` — path to the target code repo. Its `cwd` is `$REPO_DIR`.
- `CONDUCTOR_REVIEWER` — the GitHub username that Codex should request a
  review from when it opens a PR.
- Read access to `$CONDUCTOR_DIR` (via Claude Code's `additionalDirectories`
  config), so it can read the bus state and any project hub/log notes.
- For proposals with `delegated_paths`: write access to those paths in the
  knowledge base, added explicitly per-proposal.

## Invocation patterns

The prompts assume each session is booted with a verb-driven harness. Two
common patterns:

**A) Slash command / skill.** Wrap the prompt as a Claude Code skill that
boots the session. The skill is just a thin wrapper — its body says "read
this contract and run the boot ritual." Example layout:

```
~/.claude/skills/planner/SKILL.md
~/.claude/skills/builder/SKILL.md
```

Each SKILL.md frontmatter has a `description` triggering on `/planner` or
`/builder`, and the body points at the corresponding prompt file in this repo.

**B) System prompt paste.** Copy the prompt file's contents directly into
your Claude Code session's system prompt field. Simplest; no skill harness
required.

## Customization

These prompts encode protocol invariants (FSM authority, bus-mutations-only-
via-the-adapter, append discipline). Tweak the `## Boot ritual` and
`## Verbs` sections to fit your project layout — boot can read whatever
project hub / log notes you keep, and verbs can be renamed or extended.

Don't change:

- **Bus mutation discipline** (every write goes through `conductor` CLI).
- **FSM authority subset per role** (the adapter rejects violations).
- **Codex confinement to Builder** (Planner never invokes Codex).
- **Human-only `🟡 → 🟢 / ❌ / 🔵`** (the approval gate).
