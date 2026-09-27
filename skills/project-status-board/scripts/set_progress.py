#!/usr/bin/env python3
"""Set milestone progress and bump project.updatedAt in one safe step.

Usage:
    python3 set_progress.py MILESTONE_ID=PCT [MILESTONE_ID=PCT ...] [--evidence TEXT] [--file PATH]
    python3 set_progress.py --touch [--file PATH]

Examples:
    python3 set_progress.py api-auth=100 api-rate-limit=40
    python3 set_progress.py api-auth=100 --evidence "Merged in PR #42; tests pass"

The file is validated after the change and only written if it is still
valid, so a typo in an ID or percentage never corrupts the dashboard.
Structural edits (adding/renaming goals, stages, milestones) are made by
editing the JSON directly. Standard library only.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from init_dashboard import now_iso, write_json_atomic  # noqa: E402
from validate_status import DEFAULT_PATH, check, load, resolve_path, summarize  # noqa: E402


def parse_assignment(text):
    mid, sep, pct = text.partition("=")
    if not sep or not mid.strip():
        raise ValueError(f"'{text}' is not MILESTONE_ID=PCT")
    try:
        value = int(pct)
    except ValueError:
        raise ValueError(f"'{text}': progress must be a whole number 0-100") from None
    if not 0 <= value <= 100:
        raise ValueError(f"'{text}': progress must be between 0 and 100")
    return mid.strip(), value


def index_items(data):
    """Map id -> (kind, object) for every goal, stage and milestone."""
    items = {}
    for goal in data.get("goals") or []:
        items[goal.get("id")] = ("goal", goal)
        for stage in goal.get("stages") or []:
            items[stage.get("id")] = ("stage", stage)
            for milestone in stage.get("milestones") or []:
                items[milestone.get("id")] = ("milestone", milestone)
    return items


def main(argv=None):
    parser = argparse.ArgumentParser(description="Update milestone progress in project-status.json.")
    parser.add_argument("assignments", nargs="*", metavar="MILESTONE_ID=PCT")
    parser.add_argument("--file", help=f"JSON file or dashboard folder (default: {DEFAULT_PATH})")
    parser.add_argument("--evidence", help="evidence text stored on every milestone set in this call")
    parser.add_argument("--touch", action="store_true", help="only update project.updatedAt")
    args = parser.parse_args(argv)

    if not args.assignments and not args.touch:
        parser.error("give at least one MILESTONE_ID=PCT, or --touch")

    path = resolve_path(args.file)
    try:
        data = load(path)
    except FileNotFoundError:
        print(f"ERROR: {path} not found (run init_dashboard.py first)", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"ERROR: {path}: {exc}", file=sys.stderr)
        return 1

    errors, _ = check(data)
    if errors:
        print(f"ERROR: {path} is already invalid; fix it first:", file=sys.stderr)
        for msg in errors:
            print(f"  {msg}", file=sys.stderr)
        return 1

    items = index_items(data)
    changes = []
    try:
        for text in args.assignments:
            mid, value = parse_assignment(text)
            kind, obj = items.get(mid, (None, None))
            if kind is None:
                raise ValueError(f"no milestone with id '{mid}'")
            if kind != "milestone":
                raise ValueError(f"'{mid}' is a {kind}; progress is stored on milestones only "
                                 "(goal and stage progress are calculated)")
            changes.append(f"{mid}: {obj.get('progress')}% -> {value}%")
            obj["progress"] = value
            if args.evidence:
                obj["evidence"] = args.evidence
    except ValueError as exc:
        print(f"ERROR: {exc}. Nothing was written.", file=sys.stderr)
        return 1

    data["project"]["updatedAt"] = now_iso()
    errors, _ = check(data)
    if errors:
        print("ERROR: the change would make the file invalid. Nothing was written.", file=sys.stderr)
        for msg in errors:
            print(f"  {msg}", file=sys.stderr)
        return 1

    write_json_atomic(path, data)
    for line in changes:
        print(line)
    print(f"updatedAt -> {data['project']['updatedAt']}")
    print(summarize(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
