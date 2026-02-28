# Personal Agent OS Target Architecture (2026-02-28)

## Positioning

Personal Agent OS is a private, general-purpose, strongly-governed agent platform for one user.
It is not a workflow bundle. It is not a domain-only finance expert anymore.
Its core job is to classify tasks, apply governance, route to the best capability service, package delivery, and learn in a controlled way.

## Layering

1. Interaction layer
- `scripts/agent_studio.py`
- `scripts/agent_os.py`
- `scripts/agentsys.sh`
- `Makefile`

2. Agent kernel
- `core/kernel/agent_kernel.py`
- `core/kernel/models.py`
- `core/kernel/planner.py`
- `core/kernel/evaluator.py`

3. Registry / protocol
- `core/agent_service_registry.py`
- `core/registry/service_protocol.py`

4. Capability services
- `services/agent_runtime_service.py`
- `services/observability_service.py`
- `services/diagnostics_service.py`
- `services/feedback_service.py`
- `services/recommendation_service.py`
- `services/slo_service.py`
- `services/mcp_service.py`
- `services/ppt_service.py`
- `services/image_service.py`
- `services/market_service.py`
- `services/data_service.py`

5. Domain applications
- `apps/datahub/app.py`
- `apps/market_hub/app.py`
- `apps/creative_studio/app.py`

## Canonical runtime flow

1. User input enters `agent_studio` or `agent_os`.
2. Agent kernel builds `TaskSpec`, `RunRequest`, `RunContext`, `ExecutionPlan`.
3. Governance filters allowed strategies and risk.
4. Runtime delegates to `autonomy_generalist`.
5. Evaluator persists run summary, delivery bundle, and evaluation records.
6. Feedback and recommendation services consume the same run artifacts.

## Core models

- `TaskSpec`
- `RunRequest`
- `RunContext`
- `StrategyCandidate`
- `ExecutionPlan`
- `ExecutionAttempt`
- `DeliveryBundle`
- `FeedbackRecord`
- `EvaluationRecord`

## Service naming convention

- `agent.*` for agent control plane services
- `mcp.*` for external tooling orchestration
- `ppt.*` for slide/deck services
- `image.*` for image generation services
- `market.*` for market analysis services
- `data.*` for data query / analysis services

## Migration direction

1. Keep shell / Make compatibility.
2. Move business logic from `scripts/` into `core/` and `services/`.
3. Reduce direct script-to-script coupling.
4. Keep domain-heavy systems in place until the kernel/service boundary is stable.
