"""Conductor v1 adapter — single-file CLI.

See Conductor Design §8.1 for the operation surface.
"""
from __future__ import annotations

import argparse
import sys


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
