#!/usr/bin/env python3
"""Idempotent marketplace.json update script.

Modes:
  upsert-url    -- Add/replace a URL-sourced plugin entry
  upsert-inline -- Add/replace an inline (local source) plugin entry
  remove        -- Remove a plugin entry by name
"""

import argparse
import json
import sys
from pathlib import Path

MARKETPLACE_PATH = Path(".claude-plugin/marketplace.json")


def load_marketplace(path: Path) -> dict:
    return json.loads(path.read_text())


def save_marketplace(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def remove_plugin(plugins: list[dict], name: str) -> list[dict]:
    return [p for p in plugins if p.get("name") != name]


def sorted_plugins(plugins: list[dict]) -> list[dict]:
    return sorted(plugins, key=lambda p: p.get("name", ""))


def upsert_url(path: Path, plugin_json: str) -> None:
    """Add or replace a URL-sourced plugin."""
    plugin = json.loads(plugin_json)
    name = plugin["name"]

    data = load_marketplace(path)
    data["plugins"] = remove_plugin(data["plugins"], name)
    data["plugins"].append(plugin)
    data["plugins"] = sorted_plugins(data["plugins"])
    save_marketplace(path, data)
    print(f"Upserted URL plugin: {name}")


def upsert_inline(path: Path, plugin_json: str) -> None:
    """Add or replace an inline (local source) plugin."""
    plugin = json.loads(plugin_json)
    name = plugin["name"]

    data = load_marketplace(path)
    data["plugins"] = remove_plugin(data["plugins"], name)
    data["plugins"].append(plugin)
    data["plugins"] = sorted_plugins(data["plugins"])
    save_marketplace(path, data)
    print(f"Upserted inline plugin: {name}")


def remove(path: Path, name: str) -> None:
    """Remove a plugin entry by name."""
    data = load_marketplace(path)
    before = len(data["plugins"])
    data["plugins"] = remove_plugin(data["plugins"], name)
    after = len(data["plugins"])

    if before == after:
        print(f"Plugin '{name}' not found, nothing to remove.")
        return

    save_marketplace(path, data)
    print(f"Removed plugin: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update marketplace.json")
    parser.add_argument(
        "--mode",
        choices=["upsert-url", "upsert-inline", "remove"],
        required=True,
    )
    parser.add_argument(
        "--plugin-json",
        help="JSON string of the plugin entry (for upsert modes)",
    )
    parser.add_argument(
        "--name",
        help="Plugin name (for remove mode)",
    )
    parser.add_argument(
        "--path",
        default=str(MARKETPLACE_PATH),
        help="Path to marketplace.json",
    )
    args = parser.parse_args()
    path = Path(args.path)

    if args.mode in ("upsert-url", "upsert-inline"):
        if not args.plugin_json:
            print("ERROR: --plugin-json required for upsert modes", file=sys.stderr)
            sys.exit(1)
        if args.mode == "upsert-url":
            upsert_url(path, args.plugin_json)
        else:
            upsert_inline(path, args.plugin_json)
    elif args.mode == "remove":
        if not args.name:
            print("ERROR: --name required for remove mode", file=sys.stderr)
            sys.exit(1)
        remove(path, args.name)


if __name__ == "__main__":
    main()
