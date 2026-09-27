#!/usr/bin/env python3
"""Create <project-root>/project-status/ from this skill's assets.

Usage:
    python3 init_dashboard.py [--root DIR] [--name NAME] [--subtitle TEXT] [--upgrade-html]

Safe to re-run:
  * An existing project-status.json is NEVER modified or replaced.
  * An existing index.html is left alone unless --upgrade-html is given,
    in which case the old copy is kept as index.html.bak-<timestamp>.
Nothing outside the project-status/ folder is touched. Standard library only.
"""
import argparse
import filecmp
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
HTML_ASSET = ASSETS / "index.html"
JSON_TEMPLATE = ASSETS / "project-status.template.json"
DASHBOARD_DIR = "project-status"


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def write_json_atomic(path, data):
    """Write JSON via a temp file + rename so readers never see half a file."""
    fd, tmp = tempfile.mkstemp(prefix=".project-status-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def install_html(target, upgrade):
    if not target.exists():
        shutil.copyfile(HTML_ASSET, target)
        return "created"
    if filecmp.cmp(HTML_ASSET, target, shallow=False):
        return "already up to date"
    if not upgrade:
        return "kept (differs from the skill's version; re-run with --upgrade-html to replace it)"
    backup = target.with_name(f"index.html.bak-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copyfile(target, backup)
    shutil.copyfile(HTML_ASSET, target)
    return f"upgraded (previous copy saved as {backup.name})"


def install_json(target, name, subtitle):
    if target.exists():
        return "kept existing file (not modified)"
    data = json.loads(JSON_TEMPLATE.read_text(encoding="utf-8"))
    data["project"]["name"] = name
    if subtitle is not None:
        data["project"]["subtitle"] = subtitle
    data["project"]["updatedAt"] = now_iso()
    write_json_atomic(target, data)
    return "created from template (replace the placeholder goals/stages/milestones)"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Initialize the project-status dashboard.")
    parser.add_argument("--root", default=".", help="project root (default: current directory)")
    parser.add_argument("--name", help="project name for a new status file (default: root folder name)")
    parser.add_argument("--subtitle", help="one-line project summary for a new status file")
    parser.add_argument("--upgrade-html", action="store_true",
                        help="replace an existing index.html with the skill's current version")
    args = parser.parse_args(argv)

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"ERROR: project root {root} is not a directory", file=sys.stderr)
        return 1
    for asset in (HTML_ASSET, JSON_TEMPLATE):
        if not asset.is_file():
            print(f"ERROR: skill asset missing: {asset}", file=sys.stderr)
            return 1

    out = root / DASHBOARD_DIR
    if out.exists() and not out.is_dir():
        print(f"ERROR: {out} exists and is not a directory", file=sys.stderr)
        return 1
    out.mkdir(exist_ok=True)

    html_result = install_html(out / "index.html", args.upgrade_html)
    json_result = install_json(out / "project-status.json", args.name or root.name, args.subtitle)

    print(f"Dashboard folder: {out}")
    print(f"  index.html           {html_result}")
    print(f"  project-status.json  {json_result}")
    print("\nNext:")
    print(f"  python3 {Path(__file__).with_name('validate_status.py')} {out}")
    print(f"  python3 -m http.server 8765 --bind 127.0.0.1 --directory {out}")
    print("  open http://127.0.0.1:8765/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
