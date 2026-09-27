#!/usr/bin/env python3
"""Validate a project-status.json file and print a progress summary.

Usage:
    python3 validate_status.py [PATH] [--quiet]

PATH is the JSON file or the dashboard folder that contains it.
Default: ./project-status/project-status.json

Exit codes: 0 = valid (warnings allowed), 1 = invalid, 2 = file not readable.
Standard library only.
"""
import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_PATH = Path("project-status") / "project-status.json"
DATA_FILE = "project-status.json"

TOP_KEYS = {"schemaVersion", "project", "goals"}
PROJECT_KEYS = {"name", "subtitle", "updatedAt", "autoRefreshSeconds"}
GOAL_KEYS = {"id", "name", "description", "expanded", "stages"}
STAGE_KEYS = {"id", "name", "description", "expanded", "milestones"}
MILESTONE_KEYS = {"id", "name", "description", "evidence", "progress"}
PLACEHOLDER = "replace me"


# ---------------------------------------------------------------- progress
# Mirrors the dashboard: only milestones store progress; everything above
# is the plain average of the milestones underneath it.

def _avg(values):
    return sum(values) / len(values) if values else 0.0


def _clamp(value):
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def milestone_values(node):
    """Progress values of every milestone below a project, goal or stage."""
    if "milestones" in node:
        return [_clamp(m.get("progress")) for m in node.get("milestones") or [] if isinstance(m, dict)]
    children = node.get("stages") if "stages" in node else node.get("goals")
    values = []
    for child in children or []:
        if isinstance(child, dict):
            values.extend(milestone_values(child))
    return values


def progress(node):
    return _avg(milestone_values(node))


def display_percent(p):
    """Never show 0% or 100% unless it is exactly that (same as the HTML)."""
    if 0 < p < 1:
        return 1
    if 99 < p < 100:
        return 99
    return int(math.floor(p + 0.5))  # half-up, like JavaScript Math.round


def status(p):
    if p >= 100:
        return "Completed"
    if p <= 0:
        return "Not Started"
    return "In Progress"


# ---------------------------------------------------------------- checks

def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _parse_time(text):
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def check(data):
    """Return (errors, warnings) as lists of human-readable strings."""
    errors, warnings = [], []
    seen_ids = {}

    def unknown(obj, allowed, where):
        for key in obj:
            if key not in allowed:
                warnings.append(f"{where}: unknown field '{key}' (ignored by the dashboard)")

    def text_field(obj, key, where, required=True):
        value = obj.get(key)
        if value is None:
            if required:
                errors.append(f"{where}: missing required field '{key}'")
            return None
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{where}: '{key}' must be a non-empty string")
            return None
        return value

    def item_id(obj, where):
        value = text_field(obj, "id", where)
        if value is not None:
            if value in seen_ids:
                errors.append(f"{where}: duplicate id '{value}' (also used at {seen_ids[value]})")
            else:
                seen_ids[value] = where
        name = text_field(obj, "name", where)
        if name and PLACEHOLDER in name.lower():
            warnings.append(f"{where}: name '{name}' is still a template placeholder")
        text_field(obj, "description", where, required=False)
        if "expanded" in obj and not isinstance(obj["expanded"], bool):
            errors.append(f"{where}: 'expanded' must be true or false")
        return value

    def children(obj, key, where, child_label):
        value = obj.get(key)
        if value is None:
            errors.append(f"{where}: missing required field '{key}'")
            return []
        if not isinstance(value, list):
            errors.append(f"{where}: '{key}' must be a list")
            return []
        if not value:
            errors.append(f"{where}: has no {child_label}; add at least one")
        return value

    if not isinstance(data, dict):
        return ["top level must be a JSON object"], warnings
    unknown(data, TOP_KEYS, "top level")

    if "schemaVersion" in data and data["schemaVersion"] != 1:
        warnings.append(f"schemaVersion {data['schemaVersion']!r} is not 1; this validator knows version 1")

    project = data.get("project")
    if not isinstance(project, dict):
        errors.append("missing required object 'project'")
    else:
        unknown(project, PROJECT_KEYS, "project")
        text_field(project, "name", "project")
        if "subtitle" in project and not isinstance(project["subtitle"], str):
            errors.append("project: 'subtitle' must be a string")
        stamp = text_field(project, "updatedAt", "project")
        if stamp and _parse_time(stamp) is None:
            errors.append(f"project: updatedAt '{stamp}' is not an ISO 8601 timestamp "
                          "(e.g. 2026-09-26T16:48:00-07:00)")
        refresh = project.get("autoRefreshSeconds", 0)
        if not isinstance(refresh, int) or isinstance(refresh, bool) or refresh < 0:
            errors.append("project: 'autoRefreshSeconds' must be a whole number >= 0")

    goals = data.get("goals")
    if goals is None:
        errors.append("missing required list 'goals'")
        goals = []
    elif not isinstance(goals, list):
        errors.append("'goals' must be a list")
        goals = []
    elif not goals:
        errors.append("'goals' is empty; add at least one goal")

    for gi, goal in enumerate(goals):
        gw = f"goals[{gi}]"
        if not isinstance(goal, dict):
            errors.append(f"{gw}: must be an object")
            continue
        gid = item_id(goal, gw)
        gw = f"{gw} '{gid}'" if gid else gw
        unknown(goal, GOAL_KEYS, gw)
        for si, stage in enumerate(children(goal, "stages", gw, "stages")):
            sw = f"{gw} > stages[{si}]"
            if not isinstance(stage, dict):
                errors.append(f"{sw}: must be an object")
                continue
            sid = item_id(stage, sw)
            sw = f"{gw} > stages[{si}] '{sid}'" if sid else sw
            unknown(stage, STAGE_KEYS, sw)
            for mi, milestone in enumerate(children(stage, "milestones", sw, "milestones")):
                mw = f"{sw} > milestones[{mi}]"
                if not isinstance(milestone, dict):
                    errors.append(f"{mw}: must be an object")
                    continue
                mid = item_id(milestone, mw)
                mw = f"{sw} > milestones[{mi}] '{mid}'" if mid else mw
                unknown(milestone, MILESTONE_KEYS, mw)
                text_field(milestone, "evidence", mw, required=False)
                p = milestone.get("progress")
                if p is None:
                    errors.append(f"{mw}: missing required field 'progress' (0-100)")
                elif not _is_number(p):
                    errors.append(f"{mw}: progress must be a number 0-100, got {p!r}")
                elif not 0 <= p <= 100:
                    errors.append(f"{mw}: progress {p} is outside 0-100")
                elif p != int(p):
                    warnings.append(f"{mw}: progress {p} is fractional; prefer whole numbers")
    return errors, warnings


def summarize(data):
    """Compact text tree of goal and stage progress."""
    marks = {"Completed": "[x]", "In Progress": "[~]", "Not Started": "[ ]"}
    all_ms = milestone_values(data)
    overall = progress(data)
    done = sum(1 for v in all_ms if v >= 100)
    name = (data.get("project") or {}).get("name", "Untitled Project")
    lines = [f"{name}: {display_percent(overall)}% {status(overall)} "
             f"({done}/{len(all_ms)} milestones completed)"]
    for goal in data.get("goals") or []:
        gp = progress(goal)
        lines.append(f"  {marks[status(gp)]} {goal.get('name')}  {display_percent(gp)}%")
        for stage in goal.get("stages") or []:
            sp = progress(stage)
            lines.append(f"      {marks[status(sp)]} {stage.get('name')}  {display_percent(sp)}%")
    return "\n".join(lines)


def resolve_path(arg):
    path = Path(arg) if arg else DEFAULT_PATH
    return path / DATA_FILE if path.is_dir() else path


def load(path):
    """Load JSON, raising ValueError with a readable location on bad syntax."""
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate project-status.json.")
    parser.add_argument("path", nargs="?", help=f"JSON file or dashboard folder (default: {DEFAULT_PATH})")
    parser.add_argument("--quiet", action="store_true", help="print problems only, no summary")
    args = parser.parse_args(argv)

    path = resolve_path(args.path)
    try:
        data = load(path)
    except FileNotFoundError:
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 2
    except (OSError, UnicodeDecodeError) as exc:
        print(f"ERROR: cannot read {path}: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"ERROR: {path}: {exc}")
        return 1

    errors, warnings = check(data)
    for msg in errors:
        print(f"ERROR: {msg}")
    for msg in warnings:
        print(f"WARNING: {msg}")
    if errors:
        print(f"\n{path}: INVALID ({len(errors)} error(s), {len(warnings)} warning(s))")
        return 1
    print(f"{path}: OK" + (f" ({len(warnings)} warning(s))" if warnings else ""))
    if not args.quiet:
        print(summarize(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
