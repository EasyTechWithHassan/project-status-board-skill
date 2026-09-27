---
name: project-status-board
description: Creates and maintains a visual, JSON-driven project status dashboard (a static HTML page) that shows a long-running project as Goals > Stages > Milestones with calculated progress and Completed / In Progress / Not Started status. Use when the user asks to create a project dashboard or status board, track a long-running project, visualize project progress, track goals/stages/milestones, keep project status updated, or initialize the project-status-board. Also use whenever a project already contains project-status/project-status.json and meaningful work starts, progresses, or completes, or the plan changes, so the dashboard stays in sync.
license: MIT
compatibility: Requires Python 3.8+ for the helper scripts and a web browser to view the dashboard. No network access or packages needed.
metadata:
  version: "1.0.0"
---

# Project Status Board

A static dashboard at `<project-root>/project-status/`:

- `index.html`: the reusable dashboard. Never put project content in it.
- `project-status.json`: the only project-specific file. It is what you maintain.

Only **milestones** store `progress` (0–100). The dashboard calculates stage, goal and overall progress (averages of the milestones underneath), and status (0 = Not Started, 1–99 = In Progress, 100 = Completed). Never store percentages for goals, stages or the project.

Scripts live in this skill's `scripts/` folder, next to this file. Run them with `python3 <skill-dir>/scripts/<name>.py` from the project root. They use only the standard library.

## 1. First use: initialize

1. **If `project-status/project-status.json` already exists, do not re-initialize.** Go to section 2.
2. Understand the plan. Read what exists, in this order: the user's stated plan in this conversation; README; plans, roadmaps, design/architecture docs, TODO files; AGENTS.md / CLAUDE.md / GEMINI.md; the repository layout; and the git log for work already done.
3. Derive the hierarchy (see [references/usage.md](references/usage.md#structuring-a-project) for guidance):
   - **Goals**: the few major outcomes the project exists to deliver.
   - **Stages**: ordered phases within a goal.
   - **Milestones**: concrete, verifiable deliverables within a stage.
   Model only work the sources actually describe. Never invent work to fill the board.
   If the structure truly cannot be inferred, ask the user **one** concise question. Otherwise proceed without asking.
4. Create the files:
   `python3 <skill-dir>/scripts/init_dashboard.py --name "<Project Name>" --subtitle "<one line>"`
   This copies `index.html` and creates `project-status.json` from the template. It never overwrites an existing JSON file.
5. Replace the template's placeholder goal in `project-status.json` with the real hierarchy. Use stable, unique, kebab-case IDs. See [references/data-schema.md](references/data-schema.md).
6. Set each milestone's `progress` from **evidence** in the repo: code that exists, tests that pass, merged work. Leave anything unverified at 0.
7. Validate: `python3 <skill-dir>/scripts/validate_status.py`. Fix every ERROR, and fix any WARNING about placeholders.
8. Tell the user how to view the dashboard (section 4). Offer to add this line to the project's agent instructions file so future sessions keep the board in sync; add it only if they agree:
   `Keep project-status/project-status.json current using the project-status-board skill.`

## 2. Ongoing: keep it synchronized

Update the JSON when a **meaningful status change** happens:

- a milestone starts, makes meaningful progress, or is completed
- a stage or goal becomes active or completes. This follows from its milestones, so update the milestones.
- the plan materially changes: work is added, removed, split, reordered or renamed

Do **not** update after every tool call, file edit or small step. One update per meaningful change, usually at natural checkpoints (a milestone finished, a work session ending, the plan revised), is right.

How to update:

- **Progress only:** `python3 <skill-dir>/scripts/set_progress.py <milestone-id>=<pct> [...] [--evidence "..."]`. It validates before writing and sets `updatedAt` automatically.
- **Structure changes:** edit the JSON directly. Keep existing IDs stable, set `project.updatedAt` to the current time in ISO 8601 with a timezone offset, then run `validate_status.py`.

Rules:

- **Never mark work complete without evidence.** 100 means implemented and verified (tests pass, deliverable exists), not "code written". When you set 100, add a short `evidence` note (commit, PR, test run, file).
- Partial progress is an honest estimate of the share of the milestone that is done, not time spent.
- Don't silently delete milestones that have progress. If the plan drops work, say so to the user and then remove it. Don't mark dropped work 100.
- Keep existing information when editing. Change only the fields that need to change.
- Mention the update to the user in one line (e.g. "Dashboard: *Auth API* → 100%, Goal 1 now 45%").

## 3. Data format (summary)

```json
{
  "schemaVersion": 1,
  "project": { "name": "…", "subtitle": "…", "updatedAt": "2026-09-26T16:48:00-07:00", "autoRefreshSeconds": 0 },
  "goals": [
    { "id": "…", "name": "…", "description": "optional",
      "stages": [
        { "id": "…", "name": "…",
          "milestones": [ { "id": "…", "name": "…", "progress": 40, "evidence": "optional" } ] } ] } ]
}
```

Every goal needs at least one stage, and every stage at least one milestone. IDs must be unique across the file. The full schema, including optional `description`, `evidence` and `expanded`, is in [references/data-schema.md](references/data-schema.md).

## 4. Viewing

Browsers block `fetch()` from `file://`, so serve the folder:

```bash
python3 -m http.server 8765 --bind 127.0.0.1 --directory project-status
```

Then open http://127.0.0.1:8765/. **Refresh** re-reads the JSON. Setting `project.autoRefreshSeconds` (e.g. 30) makes the page poll automatically. Don't start a long-running server unless the user asks; give them the command.

## Safety

- Touch only `project-status/`, plus an agent instructions file if the user agreed to it.
- Never overwrite an existing `project-status.json` wholesale. Edit it in place.
- No secrets, credentials, internal URLs with tokens, or personal data in the JSON. It is often committed.
- The dashboard is offline-only: no CDNs, analytics or network calls. Keep it that way.

More detail on structuring, the update policy, troubleshooting and upgrading the HTML is in [references/usage.md](references/usage.md).
