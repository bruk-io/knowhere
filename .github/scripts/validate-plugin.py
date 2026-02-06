#!/usr/bin/env python3
"""Validate plugin metadata and marketplace.json schema."""

import argparse
import json
import re
import sys
from pathlib import Path

MARKETPLACE_PATH = Path(".claude-plugin/marketplace.json")

ALLOWED_CATEGORIES = frozenset({
    "database",
    "deployment",
    "design",
    "development",
    "learning",
    "monitoring",
    "productivity",
    "security",
    "testing",
})

KEBAB_CASE_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def error(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


def validate_marketplace(path: Path) -> list[str]:
    """Validate marketplace.json schema and all plugin entries."""
    errors: list[str] = []

    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, FileNotFoundError) as e:
        return [f"Failed to read {path}: {e}"]

    for field in ("$schema", "name", "description", "owner", "plugins"):
        if field not in data:
            errors.append(f"Missing top-level field: {field}")

    if "owner" in data:
        owner = data["owner"]
        if not isinstance(owner, dict):
            errors.append("owner must be an object")
        else:
            for field in ("name", "email"):
                if field not in owner:
                    errors.append(f"Missing owner field: {field}")

    if "plugins" not in data:
        return errors

    plugins = data["plugins"]
    if not isinstance(plugins, list):
        errors.append("plugins must be an array")
        return errors

    seen_names: set[str] = set()
    prev_name = ""
    for i, plugin in enumerate(plugins):
        prefix = f"plugins[{i}]"

        if not isinstance(plugin, dict):
            errors.append(f"{prefix}: must be an object")
            continue

        name = plugin.get("name")
        if not name:
            errors.append(f"{prefix}: missing name")
        elif not isinstance(name, str):
            errors.append(f"{prefix}: name must be a string")
        else:
            if not KEBAB_CASE_RE.match(name):
                errors.append(f"{prefix}: name '{name}' must be lowercase kebab-case")
            if name in seen_names:
                errors.append(f"{prefix}: duplicate name '{name}'")
            seen_names.add(name)
            if name < prev_name:
                errors.append(f"{prefix}: plugins not sorted alphabetically ('{name}' < '{prev_name}')")
            prev_name = name

        for field in ("description", "category"):
            if field not in plugin:
                errors.append(f"{prefix}: missing {field}")

        if "author" not in plugin:
            errors.append(f"{prefix}: missing author")
        elif isinstance(plugin["author"], dict):
            if "name" not in plugin["author"]:
                errors.append(f"{prefix}: author missing name")

        category = plugin.get("category")
        if category and category not in ALLOWED_CATEGORIES:
            errors.append(f"{prefix}: invalid category '{category}' (allowed: {sorted(ALLOWED_CATEGORIES)})")

        source = plugin.get("source")
        if not source:
            errors.append(f"{prefix}: missing source")
        elif isinstance(source, dict):
            if source.get("source") != "url":
                errors.append(f'{prefix}: source object must have "source": "url"')
            url = source.get("url", "")
            if not url.endswith(".git"):
                errors.append(f"{prefix}: source url must end with .git")
        elif isinstance(source, str):
            if not source.startswith("./"):
                errors.append(f"{prefix}: local source must start with ./")

    return errors


def validate_plugin_payload(payload_json: str) -> list[str]:
    """Validate a plugin payload from repository_dispatch."""
    errors: list[str] = []

    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as e:
        return [f"Invalid JSON payload: {e}"]

    plugin = payload.get("plugin")
    if not isinstance(plugin, dict):
        return ["payload must contain a 'plugin' object"]

    for field in ("name", "description", "category"):
        if field not in plugin:
            errors.append(f"plugin missing field: {field}")

    name = plugin.get("name", "")
    if name and not KEBAB_CASE_RE.match(name):
        errors.append(f"plugin name '{name}' must be lowercase kebab-case")

    category = plugin.get("category", "")
    if category and category not in ALLOWED_CATEGORIES:
        errors.append(f"invalid category '{category}'")

    if "author" not in plugin:
        errors.append("plugin missing author")

    # URL mode
    if "url" in plugin:
        if not plugin["url"].endswith(".git"):
            errors.append("plugin url must end with .git")

    # Inline mode
    if "source_repo" in payload:
        if not isinstance(payload.get("source_repo"), str):
            errors.append("source_repo must be a string")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate plugin metadata")
    parser.add_argument(
        "--mode",
        choices=["marketplace", "payload"],
        required=True,
        help="Validation mode",
    )
    parser.add_argument(
        "--payload",
        help="JSON payload string (for payload mode)",
    )
    parser.add_argument(
        "--path",
        default=str(MARKETPLACE_PATH),
        help="Path to marketplace.json (for marketplace mode)",
    )
    args = parser.parse_args()

    if args.mode == "marketplace":
        errors = validate_marketplace(Path(args.path))
    else:
        if not args.payload:
            print("ERROR: --payload required for payload mode", file=sys.stderr)
            sys.exit(1)
        errors = validate_plugin_payload(args.payload)

    if errors:
        for e in errors:
            error(e)
        sys.exit(1)
    else:
        print("Validation passed.")


if __name__ == "__main__":
    main()
