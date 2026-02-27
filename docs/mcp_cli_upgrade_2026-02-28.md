# MCP/CLI Upgrade Blueprint Landing (2026-02-28)

## Delivered Features
- `doctor`: One-command MCP environment/config/runtime health checks.
- `route-smart`: Candidate ranking with historical success rate, latency, cost, and circuit-breaker state.
- `run`: Resilient execution with retries, fallback chain, and circuit-breaker guard.
- `replay`: Call-chain replay from run logs, with dry-run support.
- `pipeline`: File-driven multi-step execution (`json` / `toml` / `yaml`) with report output.

## New Entry Points
- Script: `scripts/mcp_cli.py`
- Make targets:
  - `make mcp-doctor [probe=1]`
  - `make mcp-route-smart text='...' [topk=3] [cooldown=300] [days=14]`
  - `make mcp-run text='...' [params='{}'] [attempts=2] [dry=1] ...`
  - `make mcp-replay run_id='mcp_...' [dry=1]`
  - `make mcp-pipeline file='config/mcp_pipeline.example.json' [dry=1]`

## Data Artifacts
- Run chain logs: `日志/mcp/runs/*.json`
- Replay reports: `日志/mcp/runs/replay_*.json`
- Pipeline reports: `日志/mcp/pipelines/*.json`
- Circuit breaker state: `日志/mcp/circuit_breaker.json`
