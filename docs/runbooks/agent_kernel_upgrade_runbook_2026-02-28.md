# Agent Kernel Upgrade Runbook (2026-02-28)

## What changed

- `agent_os` is now a thin adapter over `core/kernel/agent_kernel.py`.
- `agent_service_registry` routes through typed service wrappers instead of calling most scripts directly.
- `agent_studio` supports generic service invocation through `call`.
- New persisted kernel outputs:
  - `agent_runs.jsonl`
  - `agent_evaluations.jsonl`
  - `agent_deliveries.jsonl`

## New primary operator commands

- `make agent text='...' [params='{"profile":"strict|adaptive|auto"}']`
- `make agent-studio cmd='services'`
- `make agent-studio cmd='call' service='mcp.run' params='{"text":"...","params":{"dry_run":true}}'`
- `make agent-studio cmd='call' service='ppt.generate' params='{"text":"...","params":{"page_count":8}}'`
- `make agent-studio cmd='call' service='data.query' params='{"params":{"preset":"table1_annual_core","year":2026}}'`

## Verification checklist

1. `python3 -m unittest discover -s tests -q`
2. `bash scripts/checks.sh`
3. `python3 scripts/agent_studio.py services`
4. `python3 scripts/agent_studio.py run --text '请生成本周复盘框架' --dry-run`
5. `python3 scripts/agent_studio.py call --service mcp.run --params-json '{"text":"请给出一个网页抓取方案","params":{"dry_run":true}}'`

## Safety notes

- Keep `strict` profile as default until enough feedback accumulates.
- Use `agent.feedback.pending` and `agent.feedback.add` to close the learning loop.
- Treat `market.report` as high-risk service.
- Continue to keep DataHub and report-governance flows behind their existing gates until service coverage expands.
