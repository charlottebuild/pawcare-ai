# PawCare AI - Docs Manifest

Status: Draft / Active Index  
Purpose: Docs-level entry point for the PawCare AI model specification.

This file intentionally stays short. The model spec is split across focused documents so AI coding tools can load only the relevant context.

---

## Spec Files

| File | Purpose | Read When |
| --- | --- | --- |
| `docs/constitution.md` | Safety, tone, grounding, and non-diagnostic rules | Changing prompts, recommendations, or user-facing language |
| `docs/state_schema.md` | Shared JSON state, data contracts, social context, handoff state | Building models, schemas, API payloads, persistence, tests |
| `docs/agents_definition.md` | Agent responsibilities, Orchestrator-Worker pattern, active context, handoff | Building or modifying agent workflows |
| `docs/test_cases.md` | Required edge cases and regression checks | Testing skills, agents, safety filters, and schema validation |
| `docs/guidelines.md` | Approved guideline IDs and grounding rules | Building Health Agent, Safety Agent, recovery flows, and recommendations |
| `docs/development_workflow.md` | PDCA development loop and git discipline | Planning or executing any code change |

---

## Core System Shape

```text
Care Coordinator (Orchestrator)
        |
        v
Health Agent / Behavior Agent / Safety Agent / Communication Agent
        |
        v
Structured Skills + Shared State + Safety Review
```

The Coordinator owns routing and context packaging. Worker agents stay inside their specialist domains. Safety review is required before final output.

---

## Non-Negotiables

- No diagnosis.
- No medication instructions.
- No unsupported breed or medical claims.
- All safety-relevant recommendations require `source_guideline_ids`.
- All internal agent and skill outputs must be structured JSON.
- Social stress signals such as `lip_licking`, `yawning`, `whale_eye`, `frozen`, and `stiff_body` must be preserved in state.
- Behavior changes should be checked against `docs/test_cases.md`.
- Safety-relevant recommendations should cite approved IDs from `docs/guidelines.md`.
- Code changes should follow `docs/development_workflow.md`: Plan, Do, Check, Act.
