# project-status.json schema (version 1)

One JSON object drives the whole dashboard. `validate_status.py` checks every rule below.

## Top level

| Field | Type | Required | Notes |
|---|---|---|---|
| `schemaVersion` | integer | no | `1`. Reserved for future format changes. |
| `project` | object | **yes** | See below. |
| `goals` | array | **yes** | At least one goal. The order shown is the order in the file. |

## `project`

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | **yes** | Shown as the page title. |
| `subtitle` | string | no | One-line summary under the title. |
| `updatedAt` | string | **yes** | ISO 8601 with a timezone offset, e.g. `2026-09-26T16:48:00-07:00` or `…Z`. Update it whenever the status changes. |
| `autoRefreshSeconds` | integer ≥ 0 | no | `0` (the default) means manual Refresh only. Values below 5 are treated as 5. |

## Goal

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | **yes** | Unique across the whole file. |
| `name` | string | **yes** | |
| `description` | string | no | One short line under the name. |
| `expanded` | boolean | no | Forces the default open/closed state. Normally omit it (see "Default expansion"). |
| `stages` | array | **yes** | At least one stage. |

## Stage

It has the same fields as a goal, except `milestones` (an array with at least one item) replaces `stages`.

## Milestone

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | **yes** | Unique across the whole file. |
| `name` | string | **yes** | |
| `progress` | number 0–100 | **yes** | Use whole numbers. The only stored percentage. |
| `description` | string | no | Shown when the milestone row is expanded. |
| `evidence` | string | no | Why the progress is what it is (commit, PR, test run). Shown when expanded. Expected when `progress` is 100. |

A milestone with `description` or `evidence` gets its own expand toggle. One without either is a plain row.

Unknown fields are ignored by the dashboard and reported as warnings by the validator (usually a typo).

## Calculated values (never stored)

| Level | Progress |
|---|---|
| Stage | average `progress` of its milestones |
| Goal | average `progress` of **all milestones in the goal**, so bigger stages weigh more |
| Project | average `progress` of all milestones in the project |

Status comes from the progress value:

| Progress | Status | Colour |
|---|---|---|
| exactly 0 | Not Started | gray |
| above 0 and below 100 | In Progress | blue |
| exactly 100 (every milestone underneath at 100) | Completed | green |

The percentages shown are rounded, but they never show `0%` or `100%` unless the value is exactly that. So 99.6% shows as `99%` and In Progress, never as a false "Completed".

## Default expansion

On first load:

- Goals that are In Progress are open. If none are, but the project has started, the first unfinished goal is open.
- Inside an open goal, In Progress stages are open, or the first unfinished stage if none are.
- Everything else is collapsed, including completed and future goals.

An explicit `expanded` in the JSON overrides this. The viewer's own clicks override both, and last for that browser tab.

## IDs

- Use lowercase kebab-case, e.g. `auth`, `auth-api`, `auth-api-login-endpoint`. Prefixing with the parent ID keeps IDs unique and readable.
- Keep IDs stable once they exist. Renaming the `name` is fine; changing the `id` loses the viewer's expand state.
- `set_progress.py` finds milestones by ID.

## Complete example

```json
{
  "schemaVersion": 1,
  "project": {
    "name": "Inventory Service",
    "subtitle": "REST service and dashboard for warehouse stock.",
    "updatedAt": "2026-09-26T16:48:00-07:00",
    "autoRefreshSeconds": 0
  },
  "goals": [
    {
      "id": "core-api",
      "name": "Core API",
      "description": "CRUD + search over stock items.",
      "stages": [
        {
          "id": "core-api-foundation",
          "name": "Foundation",
          "milestones": [
            { "id": "core-api-schema", "name": "Database schema", "progress": 100,
              "evidence": "migrations/001_init.sql; tests/test_schema.py passes" },
            { "id": "core-api-crud", "name": "CRUD endpoints", "progress": 60,
              "description": "Create/read/update done; delete pending." }
          ]
        },
        {
          "id": "core-api-search",
          "name": "Search",
          "milestones": [
            { "id": "core-api-search-index", "name": "Search index", "progress": 0 }
          ]
        }
      ]
    }
  ]
}
```

Here the stage *Foundation* is at 80% (the average of 100 and 60), the goal *Core API* is at 53% (160 / 3), and the project is at 53%.
