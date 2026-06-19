from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

from cpr.core.builtin_tree import SDKMAN_TREE
from cpr.core.model import load_command_tree, load_command_tree_file
from cpr.core.slash import SlashCommandParser


def main(argv: list[str] | None = None) -> int:
    log_path = Path.home() / ".cpr" / "logs" / "cpr.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=str(log_path), level=logging.WARNING)
    print(f"log: {log_path}")
    parser = argparse.ArgumentParser(prog="python -m cpr")
    parser.add_argument("--check-tree", action="store_true")
    parser.add_argument("--slash-parse")
    args = parser.parse_args(argv)
    try:
        data_path = Path("data/sdkman.yaml")
        tree = load_command_tree_file(data_path) if data_path.exists() else load_command_tree(SDKMAN_TREE)
    except Exception as exc:
        print(f"failed to load command tree: {exc}", file=sys.stderr)
        return 2
    if args.check_tree:
        print(f"ok: {len(tree.nodes)} nodes")
        return 0
    if args.slash_parse is not None:
        command = SlashCommandParser().parse(args.slash_parse)
        if command is None:
            print("not slash")
        else:
            print(f"name={command.name} args={command.args}")
        return 0
    from cpr.tui.app import run_app

    run_app(tree)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
