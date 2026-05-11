# PawCare AI - Agents Definition

Status: Draft / Active Design  
Purpose: Define the multi-agent collaboration model, agent boundaries, handoff rules, and Orchestrator-Worker execution pattern.
Depends On: `docs/constitution.md`, `docs/state_schema.md`
Dependency Rule: All Worker Agent inputs and outputs must strictly map to `active_context`, `agent_outputs`, `handoff`, `risk_assessment`, and `safety_review` as defined in `docs/state_schema.md`.

This document explains how PawCare AI agents work together. It should be updated whenever agent responsibilities, handoff behavior, or workflow routing changes.

---

## 1. Architecture

```text
Frontend (React / Mobile UI)
        |
        v
Backend API Layer
        |
        v
Care Coordinator (Orchestrator)
        |
        v
-------------------------------------------------
| Health Agent        | Behavior Agent           |
| Safety Agent        | Communication Agent      |
-------------------------------------------------
        |
        v
Agent-owned Skills
        |
        v
PostgreSQL + Redis
        |
        v
Logging / Evaluation / Monitoring
```

The system uses an Orchestrator-Worker pattern.

The Care Coordinator is the Orchestrator. It owns workflow state, task routing, context packaging, conflict resolution, and final assembly.

Health Agent, Behavior Agent, Safety Agent, and Communication Agent are Workers. They operate within their professional boundaries and only receive the active context they need.

---

## 2. Orchestrator-Worker Pattern

### 2.1 Care Coordinator as Orchestrator

The Care Coordinator is not a passive message router.

Responsibilities:

- maintain global workflow state
- decide which agents should run
- build `active_context` for each worker
- hide irrelevant or unsafe context from workers
- preserve `source_guideline_ids`
- track unresolved conflicts
- reconcile worker conclusions
- require Safety Agent approval before final output

The Coordinator should ask narrow questions.

Example Behavior Agent task:

```text
Health Agent marked this as moderate risk because appetite is below baseline.
From a behavior perspective, do the social and environmental observations suggest stress from a new setting?
Return structured JSON only.
```

Example Safety Agent task:

```text
Review this recommendation for diagnosis, medication advice, unsupported certainty, missing guideline IDs, and over-reassurance.
Return approved, approved_with_rewrites, or blocked_needs_human_review.
```

### 2.2 Workers as Specialist Agents

Worker agents must:

- stay inside their assigned domain
- return structured output
- cite `source_guideline_ids`
- write concise reasoning traces
- identify missing information
- avoid final user-facing advice unless explicitly assigned
- return proposed updates instead of mutating global state directly

Worker agents must not:

- overwrite global state directly
- diagnose
- give medication instructions
- make unsupported breed claims
- ignore baseline
- emit final owner messages unless they are the Communication Agent

### 2.3 Isolation Rule

The Coordinator owns write access to the full workflow state.

Worker agents do not receive the full state object by default. Health Agent and Behavior Agent can only see the scoped copy packaged in `active_context`.

Workers must return a `proposed_update` object to the Coordinator. The Coordinator decides whether to merge, reject, revise, or escalate the proposal.

Required worker response shape:

```json
{
  "agent": "BehaviorAgent",
  "input_active_context_id": "ctx_001",
  "conclusion": "moderate social stress",
  "confidence": 0.84,
  "missing_information": [
    "whether this dog has guarded chews before"
  ],
  "proposed_update": {
    "target_path": "risk_assessment.risk_factors",
    "operation": "append",
    "value": "stress signals near high-value resource"
  },
  "reasoning_trace": "Lip licking, freezing, and stiff body occurred when a larger dog approached a chew.",
  "source_guideline_ids": [
    "GL_SOCIAL_STRESS_001",
    "GL_RESOURCE_GUARDING_001"
  ]
}
```

Coordinator merge rules:

- validate proposed updates against `docs/state_schema.md`
- preserve the original worker output in `agent_outputs`
- write accepted changes into global state
- record rejected or conflicting proposals in `current_session_state.pending_conflicts`
- never allow a worker proposal to bypass Safety Agent review

---

## 3. Agent Responsibilities

### 3.1 Health Agent

Focus:

- appetite
- stool quality
- vomiting
- lethargy
- mobility
- coughing
- hydration-related signals
- symptom severity and duration

Reads:

- `active_context`
- `observations`
- `health_baseline`
- relevant guideline snippets
- recent health history

Writes:

- `agent_outputs`
- health-domain risk factors
- missing health information
- recommended health escalation conditions

Must not:

- diagnose disease
- name a disease as fact
- recommend medication
- dismiss symptoms as harmless

### 3.2 Behavior Agent

Focus:

- stress
- anxiety
- environmental change
- body language
- multi-dog interaction
- resource guarding
- large-dog/small-dog dynamics
- deviation from behavioral baseline

Reads:

- `active_context`
- `observations.social_context`
- `behavioral_baseline`
- `resource_guarding_profile`
- relevant guideline snippets
- Health Agent summary if provided by Coordinator

Writes:

- `agent_outputs`
- behavior-domain risk factors
- social stress interpretation
- missing behavior information
- recommended management actions

Important trigger signals:

- `lip_licking`
- `yawning`
- `whale_eye`
- `frozen`
- `stiff_body`
- `avoidance`
- `turning_away`
- `blocking`
- `hovering`
- `growl`
- `air_snap`

Resource-sensitive triggers:

- food
- treats
- chews
- toys
- bed
- crate
- doorway
- human attention
- water bowl

Must not:

- call a dog aggressive as a fixed trait based on one event
- ignore subtle stress signals
- treat lack of growling as proof of safety
- override physical health concern

### 3.3 Safety Agent

Focus:

- constitutional compliance
- non-diagnostic language
- medication-advice blocking
- grounding enforcement
- excessive reassurance removal
- escalation clarity

Reads:

- recommendation candidate
- `agent_outputs`
- `risk_assessment`
- `source_guideline_ids`
- `docs/constitution.md` rules

Writes:

- `safety_review`
- rewrites
- blocked content list

Must block or rewrite:

- diagnosis
- medication instructions
- unsupported certainty
- "don't worry" language
- recommendations without guideline IDs
- claims that symptoms can be ignored

### 3.4 Communication Agent

Focus:

- owner-facing update
- sitter-facing summary
- calm wording
- appropriate urgency
- concise explanation

Reads:

- safety-approved recommendation
- `risk_assessment`
- `safety_review`
- owner communication preferences

Writes:

- `final_recommendation.owner_message`
- final user-facing summary

Must not:

- bypass Safety Agent
- add new medical or behavioral claims
- soften urgent escalation language below the approved risk level
- remove required escalation conditions

---

## 4. Handoff Protocol

Agent-to-agent handoff must use structured state, not prose-only summaries.

Required handoff fields:

- `from_agent`
- `to_agent`
- `dog_id`
- `workflow_id`
- `current_observations`
- `conflicting_signals`
- `agent_reasoning_trace`
- `source_guideline_ids`

Example:

```json
{
  "from_agent": "BehaviorAgent",
  "to_agent": "CareCoordinator",
  "dog_id": "dog_123",
  "workflow_id": "wf_20260508_001",
  "current_observations": [
    "obs_001"
  ],
  "conflicting_signals": [
    {
      "signal": "low_appetite_after_new_dog_interaction",
      "behavior_interpretation": "possible stress response",
      "health_interpretation": "appetite below baseline may raise health risk",
      "requires_resolution": true
    }
  ],
  "agent_reasoning_trace": [
    {
      "agent": "BehaviorAgent",
      "conclusion": "stress may be contributing",
      "reasoning": "Lip licking and freezing occurred near a larger dog and high-value chew.",
      "source_guideline_ids": [
        "GL_SOCIAL_STRESS_001",
        "GL_RESOURCE_GUARDING_001"
      ]
    }
  ],
  "source_guideline_ids": [
    "GL_SOCIAL_STRESS_001",
    "GL_RESOURCE_GUARDING_001"
  ]
}
```

---

## 5. Active Context

`active_context` is the context package dynamically prepared by the Care Coordinator for a specific worker.

The purpose is to avoid giving every worker the entire global state. Each worker should see enough to do its job, but not so much that it drifts into another agent's domain.

Example for Behavior Agent:

```json
{
  "active_context": {
    "target_agent": "BehaviorAgent",
    "task": "Assess whether the social observation indicates stress, resource concern, or normal play.",
    "current_observation_ids": [
      "obs_001"
    ],
    "relevant_baseline": {
      "large_dog_reaction": "neutral",
      "resource_guarding_profile": {
        "toy_guarding": "mild",
        "known_guarded_resources": [
          "high_value_chews"
        ]
      }
    },
    "prior_agent_summary": {
      "agent": "HealthAgent",
      "conclusion": "no physical injury reported, appetite context unknown",
      "risk_band": "low_to_moderate"
    },
    "guideline_ids_allowed": [
      "GL_SOCIAL_STRESS_001",
      "GL_RESOURCE_GUARDING_001"
    ],
    "output_contract": "agent_outputs.BehaviorAgent"
  }
}
```

Rules:

- Coordinator creates `active_context`.
- Worker reads `active_context`.
- Worker does not mutate `active_context`.
- Worker output must reference the observation IDs and guideline IDs provided.
- If context is insufficient, worker must write `missing_information` rather than guessing.

---

## 6. Conflict Resolution

Conflicts should be written to `current_session_state.pending_conflicts`.

Common conflict types:

- `behavior_vs_health`
- `risk_level_disagreement`
- `baseline_conflict`
- `guideline_conflict`
- `owner_instruction_vs_safety`
- `missing_information`

Coordinator resolution options:

- request more information
- run another agent
- choose the higher safety risk
- preserve both interpretations in final summary
- escalate to owner/vet guidance
- block final output until human review

Example:

```text
Health Agent says reduced appetite increases concern.
Behavior Agent says new environment and large-dog stress may explain the behavior.
Coordinator result: treat as mixed domain, monitor closely, notify owner, define escalation conditions.
```

---

## 7. Default Workflow

```text
User logs event
-> LogExtractor creates structured observation
-> ContextHydrator loads profile, baseline, and recent history
-> Coordinator builds active_context for relevant agents
-> Health Agent and/or Behavior Agent analyze their domain
-> Coordinator records conflicts and reconciles conclusions
-> RiskEvaluator produces risk assessment
-> SuggestionBuilder creates candidate recommendation
-> Safety Agent validates or rewrites
-> Communication Agent formats final message
-> Final result is logged
```

No final recommendation may skip Safety Agent review.

---

## 8. Implementation Checklist

Before changing any agent:

1. Confirm its read fields.
2. Confirm its write fields.
3. Confirm its handoff shape.
4. Confirm relevant `source_guideline_ids`.
5. Confirm applicable safety rules in `docs/constitution.md`.
6. Update `docs/state_schema.md` if state shape changes.
7. Update `docs/test_cases.md` when tests are introduced.
