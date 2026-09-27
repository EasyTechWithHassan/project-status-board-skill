# Usage guide

## Structuring a project

Aim for a board a person can read in ten seconds when collapsed.

**Goals** are the major outcomes: what someone would list if asked "what is this project for?". There are typically 1–6.
- Good: "Public REST API", "Production deployment", "Data migration".
- Bad: "Write code", "Misc", "Phase 1" (a phase is a stage, not an outcome).

**Stages** are ordered phases within one goal, usually 1–6 per goal, e.g. Design → Build → Harden → Release. A goal with a single stage is fine. Don't split artificially.

**Milestones** are concrete, verifiable deliverables, typically 2–8 per stage. Each should have an obvious "done" test.
- Good: "Login endpoint with tests", "Terraform for VPC applied to staging".
- Bad: "Work on auth", "Research".

Sources, in order of trust:
1. What the user said in this conversation.
2. Written plans: README, ROADMAP, PLAN, docs/, design/architecture docs, TODO/TASKS files, issue lists checked into the repo.
3. Agent instruction files: AGENTS.md, CLAUDE.md, GEMINI.md.
4. Repository structure and git history. Use these to judge what is **done**, not to invent new goals.

If sources disagree, follow the most recent explicit user statement. If there is no plan at all (e.g. an empty repo and no stated intent), ask one question, such as: *"What are the main goals of this project, and roughly what steps does each involve?"*

Keep names short (under ~60 characters). Put extra context in `description`.

## Setting progress honestly

| Evidence | Progress |
|---|---|
| Nothing done | 0 |
| Started: scaffolding, a first draft | 10–30 |
| Core of it works, gaps remain | 40–80 |
| Implemented, final verification pending | 85–95 |
| Implemented **and** verified (tests pass, deployed, reviewed as the plan requires) | 100 |

When unsure between two values, pick the lower one. When a milestone reaches 100, record the evidence:

```bash
python3 <skill-dir>/scripts/set_progress.py auth-login=100 --evidence "PR #42 merged; pytest tests/auth passes"
```

## Update policy

Update when:

- a milestone starts (0 → >0), moves meaningfully (roughly 20 points or more), or completes;
- work is added, removed, split, reordered or renamed in the plan;
- a session ends with progress not yet recorded.

Don't update for individual file edits, tool calls, failed attempts or refactors that don't change deliverable status.

Batch several milestone changes into one `set_progress.py` call where you can.

When the plan changes:

- **Add work:** append milestones or stages with new unique IDs and `progress: 0`.
- **Remove work:** only when the plan truly drops it. Tell the user first if it had progress.
- **Split a milestone:** replace it with the parts, carrying the done portion over honestly.
- **Reorder:** move array items. IDs stay the same.

After any hand edit, set `project.updatedAt` and run:

```bash
python3 <skill-dir>/scripts/validate_status.py
```

## Commands

Run these from the project root. `<skill-dir>` is the folder containing SKILL.md.

| Task | Command |
|---|---|
| Initialize (safe to re-run) | `python3 <skill-dir>/scripts/init_dashboard.py --name "Name" --subtitle "Summary"` |
| Validate and show a summary | `python3 <skill-dir>/scripts/validate_status.py` |
| Validate another file | `python3 <skill-dir>/scripts/validate_status.py path/to/project-status.json` |
| Set progress | `python3 <skill-dir>/scripts/set_progress.py ID=PCT [ID=PCT ...] [--evidence "..."]` |
| Bump the timestamp only | `python3 <skill-dir>/scripts/set_progress.py --touch` |
| Upgrade index.html to the skill's current version | `python3 <skill-dir>/scripts/init_dashboard.py --upgrade-html` (backs up the old one) |
| Serve the dashboard | `python3 -m http.server 8765 --bind 127.0.0.1 --directory project-status` |

Exit codes for the validator: `0` valid, `1` invalid, `2` file missing or unreadable.

## Viewing

- Serve the folder, then open `http://127.0.0.1:8765/`. `--bind 127.0.0.1` keeps it private to your machine.
- To use another port, change `8765`.
- To view a JSON file elsewhere, use `http://127.0.0.1:8765/?data=<relative-or-absolute-url>`.
- **Refresh** re-reads the JSON without losing what you expanded. If the JSON is broken, a notice appears and the last good data stays on screen.
- Opening `index.html` directly (`file://`) shows a notice with the serve command. Browsers block local file reads.

## Keeping future sessions in sync

Skills activate per session, from their description. To make every future session remember the board, the user can add one line to the project's agent instructions file (AGENTS.md, CLAUDE.md or GEMINI.md):

```text
Keep project-status/project-status.json current using the project-status-board skill.
```

Only add it with the user's agreement.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Browsers block reading … from a file:// page" | Serve the folder (see above). |
| "Could not load project-status.json: HTTP 404" | The server is running from the wrong folder. Use `--directory project-status`. |
| "invalid JSON" notice | Run `validate_status.py`. It reports the line and column. |
| A stage shows 99%, not Completed | At least one milestone is below 100. That is by design. |
| Goal % ≠ average of its stage % | Goal progress averages milestones, not stages. That is by design. |
| Changes not visible | Press Refresh. The page never caches the JSON. |
