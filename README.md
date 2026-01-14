# fb-agent — Frappe Manager Backup Agent

Runs on production servers next to `fm` and exposes a strict allowlisted API.

## Run (zero-config)

After installing with `pipx` from GitHub:

- `fb-agent run`

On first run it auto-discovers `fm`, discovers stacks/sites via `fm list`, generates a stable `agent_id`, announces itself to the Dashboard automatically, and exposes its API.


