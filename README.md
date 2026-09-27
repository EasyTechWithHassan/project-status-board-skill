# Project Status Board

A self-contained, parameterized project dashboard for Claude Code.

## Files
- `project-status-board.html` — complete frontend (HTML + CSS + JS)
- `project-status.json` — sample external data source

## Quick use
For easiest editing, run a local server in this folder:

```bash
python3 -m http.server 8080
```

Then open:

```text
http://localhost:8080/project-status-board.html?data=project-status.json
```

Claude Code can update only `project-status.json`; the dashboard calculates:
- milestone status from `progress`
- stage progress from its milestones
- goal progress from all milestones under that goal
- overall project progress from all milestones

## Status logic
- `0` = Not Started
- `1–99` = In Progress
- `100` = Completed

## Example milestone
```json
{
  "id": "g1-s2-m3",
  "name": "Milestone 3",
  "progress": 30
}
```

Set `"expanded": true` on a goal/stage if you want it open by default.

Set `"autoRefreshSeconds": 30` in `project` if you want the HTML to re-read the external JSON automatically every 30 seconds.
