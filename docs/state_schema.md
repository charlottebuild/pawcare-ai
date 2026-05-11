# PawCare AI - State Schema

Status: Draft / Active Contract  
Owner: Care Coordinator  
Purpose: Define the shared state object used by all agents, skills, handoffs, persistence, tests, and safety checks.
Depends On: `docs/constitution.md`
Dependency Rule: JSON contracts in this file must comply with the safety, grounding, and non-diagnostic requirements in `docs/constitution.md`.

This document is the administrative map of PawCare AI. If `docs/constitution.md` defines the safety law, this file defines the shared blackboard that the Care Coordinator governs.

All future agent behavior, skill output, database design, and test fixtures must align with this schema.

---

## 1. State Principles

### 1.1 State Is Shared Infrastructure

The state object is the single source of truth during a workflow.

Agents must not invent private hidden context. If an observation, assumption, conflict, guideline, or risk decision matters, it must be represented in state.

### 1.2 Structured Before Conversational

Internal state must be JSON-compatible and schema-valid.

Conversation is allowed only at the final communication layer. Health, behavior, logging, retrieval, and safety operations must produce structured fields.

### 1.3 Baseline Before Judgment

Risk and behavior interpretation must compare current observations against the dog's baseline.

The same signal may have different meaning for different dogs:

- A chronically anxious dog lip licking once during a new-dog introduction may be low to moderate concern.
- A normally confident dog freezing, lip licking, and avoiding food may be a stronger deviation.

### 1.4 Conflicts Are First-Class Data

Agent disagreement must not be hidden in prose.

If Health Agent, Behavior Agent, Safety Agent, or Coordinator interpretations conflict, the conflict must be written into `current_session_state.pending_conflicts`.

### 1.5 Social Signals Matter

Subtle social signals are safety-relevant.

The schema must preserve stress and body-language details such as:

- lip licking
- yawning
- whale eye
- freezing
- stiff body
- avoidance
- displacement sniffing
- resource guarding
- blocking access
- hovering near food, toys, doors, beds, or humans

---

## 2. Top-Level State

```json
{
  "schema_version": "0.1.0",
  "workflow_id": "wf_20260508_001",
  "dog_id": "dog_123",
  "dog_profile": {},
  "behavioral_baseline": {},
  "health_baseline": {},
  "current_session_state": {},
  "active_context": {},
  "observations": [],
  "derived_patterns": [],
  "risk_assessment": {},
  "agent_outputs": [],
  "handoff": {},
  "safety_review": {},
  "final_recommendation": {}
}
```

Required top-level fields:

| Field | Type | Required | Owner | Description |
| --- | --- | --- | --- | --- |
| `schema_version` | string | yes | System | State schema version. |
| `workflow_id` | string | yes | Care Coordinator | Unique workflow/run ID. |
| `dog_id` | string | yes | Care Coordinator | Primary dog ID. |
| `dog_profile` | object | yes | ContextHydrator | Stable dog identity and owner context. |
| `behavioral_baseline` | object | yes | ContextHydrator | Normal behavior and social profile. |
| `health_baseline` | object | yes | ContextHydrator | Normal physical/health patterns. |
| `current_session_state` | object | yes | Care Coordinator | Active workflow state and unresolved conflicts. |
| `active_context` | object | yes | Care Coordinator | Agent-specific context package for the current worker. |
| `observations` | array | yes | LogExtractor | Structured current and recent observations. |
| `derived_patterns` | array | yes | PatternAnalyzer | Trends and baseline deviations. |
| `risk_assessment` | object | yes | RiskEvaluator | Current risk level and rationale. |
| `agent_outputs` | array | yes | Agents | Structured outputs from each agent. |
| `handoff` | object | yes | Care Coordinator | Current handoff package. |
| `safety_review` | object | yes | Safety Agent | Safety validation status. |
| `final_recommendation` | object | no | Communication Agent | Final owner/user-facing result. |

---

## 3. Dog Profile

```json
{
  "dog_profile": {
    "id": "dog_123",
    "name": "Mochi",
    "breed": "Shiba Inu",
    "age_years": 4,
    "weight_kg": 11.5,
    "sex": "female",
    "spayed_neutered": true,
    "owner_contact_preferences": {
      "notify_for_moderate_risk": true,
      "preferred_channel": "text",
      "tone_preference": "calm_and_brief"
    },
    "care_notes": [
      "May refuse breakfast in unfamiliar homes.",
      "Owner wants updates for any appetite change lasting more than one meal."
    ]
  }
}
```

Guidelines:

- `breed` must not be used for unsupported assumptions unless a guideline source explicitly supports the claim.
- `care_notes` may affect communication and escalation thresholds, but they do not override safety rules.

---

## 4. Behavioral Baseline

```json
{
  "behavioral_baseline": {
    "general_temperament": "food_motivated",
    "energy_level": "medium",
    "confidence_level": "medium",
    "separation_comfort": "moderate_anxiety",
    "social_profile": {
      "large_dog_reaction": "neutral",
      "small_dog_reaction": "friendly",
      "human_reaction": "friendly",
      "prey_drive_level": 4,
      "play_style": "chase_and_pause",
      "known_triggers": [
        "fast_movements",
        "direct_staring",
        "bikes"
      ],
      "stress_signals_typical": [
        "lip_licking",
        "turning_away"
      ],
      "recovery_pattern": "usually_recovers_with_distance"
    },
    "resource_guarding_profile": {
      "food_guarding": "none_known",
      "toy_guarding": "mild",
      "space_guarding": "none_known",
      "human_guarding": "unknown",
      "known_guarded_resources": [
        "high_value_chews"
      ]
    }
  }
}
```

Allowed enum values:

| Field | Allowed Values |
| --- | --- |
| `general_temperament` | `food_motivated`, `anxious`, `high_energy`, `calm`, `reserved`, `confident`, `unknown` |
| `energy_level` | `low`, `medium`, `high`, `unknown` |
| `confidence_level` | `low`, `medium`, `high`, `unknown` |
| `large_dog_reaction` | `fearful`, `neutral`, `friendly`, `reactive`, `avoidant`, `unknown` |
| `small_dog_reaction` | `fearful`, `neutral`, `friendly`, `reactive`, `avoidant`, `unknown` |
| `human_reaction` | `fearful`, `neutral`, `friendly`, `reactive`, `avoidant`, `unknown` |
| `resource_guarding_profile.*` | `none_known`, `mild`, `moderate`, `severe`, `unknown` |

`prey_drive_level` is an integer from `1` to `10`.

---

## 5. Health Baseline

```json
{
  "health_baseline": {
    "normal_appetite": "high",
    "normal_stool_quality": "firm",
    "normal_stool_frequency_per_day": 2,
    "normal_water_intake": "medium",
    "normal_activity_level": "medium",
    "known_medical_notes": [
      "Sensitive stomach during food transitions."
    ],
    "owner_escalation_rules": [
      "Notify owner if refusing more than one meal.",
      "Notify owner immediately for vomiting or bloody stool."
    ]
  }
}
```

Allowed enum values:

| Field | Allowed Values |
| --- | --- |
| `normal_appetite` | `low`, `medium`, `high`, `variable`, `unknown` |
| `normal_stool_quality` | `firm`, `soft`, `loose`, `variable`, `unknown` |
| `normal_water_intake` | `low`, `medium`, `high`, `variable`, `unknown` |
| `normal_activity_level` | `low`, `medium`, `high`, `variable`, `unknown` |

---

## 6. Current Session State

```json
{
  "current_session_state": {
    "is_active": true,
    "session_started_at": "2026-05-08T09:00:00-07:00",
    "last_interaction_timestamp": "2026-05-08T09:20:00-07:00",
    "environment": {
      "location_type": "sitter_home",
      "new_environment": true,
      "other_animals_present": true,
      "other_dog_ids": [
        "dog_456"
      ],
      "notable_context": [
        "first_day_of_sitting",
        "large_dog_present"
      ]
    },
    "pending_conflicts": [
      {
        "conflict_id": "conflict_001",
        "type": "behavior_vs_health",
        "description": "Behavior Agent detected stress signals, while Health Agent did not find physical red flags.",
        "involved_agents": [
          "BehaviorAgent",
          "HealthAgent"
        ],
        "resolved": false,
        "resolution": null
      }
    ]
  }
}
```

Allowed `pending_conflicts.type` values:

- `behavior_vs_health`
- `risk_level_disagreement`
- `baseline_conflict`
- `guideline_conflict`
- `owner_instruction_vs_safety`
- `missing_information`

---

## 7. Active Context

`active_context` is the scoped context package prepared by the Care Coordinator for the currently running worker agent.

The Coordinator uses this field to prevent context overload and semantic drift. Workers should receive enough context to complete their specialist task, but not the entire global state by default.

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
      "small_dog_reaction": "friendly",
      "resource_guarding_profile": {
        "toy_guarding": "mild",
        "known_guarded_resources": [
          "high_value_chews"
        ]
      }
    },
    "prior_agent_summary": {
      "agent": "HealthAgent",
      "conclusion": "no physical injury reported",
      "risk_band": "low_to_moderate"
    },
    "allowed_guideline_ids": [
      "GL_SOCIAL_STRESS_001",
      "GL_RESOURCE_GUARDING_001"
    ],
    "required_output_path": "agent_outputs",
    "must_answer": [
      "Does this interaction include stress signals?",
      "Is a resource involved?",
      "What information is missing?"
    ]
  }
}
```

Rules:

- `CareCoordinator` writes `active_context`.
- Worker agents read `active_context`.
- Worker agents must not mutate `active_context`.
- Worker agents must write results to their assigned output path.
- If `active_context` is insufficient, the worker must report `missing_information` instead of guessing.

---

## 8. Observations

`observations` stores structured facts extracted from sitter input, sensor input, scheduled scans, or agent-verified history.

```json
{
  "observations": [
    {
      "observation_id": "obs_001",
      "timestamp": "2026-05-08T09:15:00-07:00",
      "source": "user_log",
      "category": "social_interaction",
      "raw_text": "Mochi froze and licked her lips when the large dog came near her chew.",
      "confidence": 0.91,
      "entity_involved": {
        "type": "large_dog",
        "id": "dog_456",
        "name": "Bear",
        "relative_size": "larger"
      },
      "social_context": {
        "interaction_type": "resource_proximity",
        "initiator": "other_dog",
        "distance": "near",
        "resource_involved": {
          "present": true,
          "type": "chew",
          "ownership": "primary_dog"
        },
        "signals": {
          "body_language": [
            "lip_licking",
            "frozen",
            "stiff_body"
          ],
          "vocalization": [
            "silent"
          ],
          "posture": "frozen",
          "movement": "avoidant"
        },
        "handler_intervention": {
          "occurred": true,
          "type": "increased_distance",
          "result": "deescalated"
        }
      },
      "health_context": null,
      "severity_score": 6,
      "source_guideline_ids": [
        "GL_SOCIAL_STRESS_001",
        "GL_RESOURCE_GUARDING_001"
      ]
    }
  ]
}
```

### 7.1 Observation Categories

Allowed `category` values:

- `food_intake`
- `water_intake`
- `stool`
- `urination`
- `vomiting`
- `energy`
- `mobility`
- `sleep`
- `social_interaction`
- `environment_change`
- `owner_instruction`
- `medication_note`
- `other`

### 7.2 Social Context

`social_context` is required when `category` is `social_interaction`.

```json
{
  "social_context": {
    "interaction_type": "greeting",
    "initiator": "primary_dog",
    "distance": "same_room",
    "duration_seconds": 20,
    "resource_involved": {
      "present": false,
      "type": null,
      "ownership": null
    },
    "signals": {
      "body_language": [
        "lip_licking",
        "yawning"
      ],
      "vocalization": [
        "silent"
      ],
      "posture": "upright",
      "movement": "turning_away"
    },
    "handler_intervention": {
      "occurred": false,
      "type": null,
      "result": null
    }
  }
}
```

Allowed `interaction_type` values:

- `greeting`
- `parallel_presence`
- `play`
- `resource_proximity`
- `resource_conflict`
- `doorway_or_threshold`
- `human_attention`
- `walk_passing`
- `chase`
- `staring`
- `unknown`

Allowed `initiator` values:

- `primary_dog`
- `other_dog`
- `human`
- `unclear`

Allowed `distance` values:

- `across_room`
- `same_room`
- `near`
- `direct_contact`
- `blocked_access`
- `unknown`

Allowed `resource_involved.type` values:

- `food`
- `treat`
- `chew`
- `toy`
- `bed`
- `crate`
- `water_bowl`
- `human_attention`
- `doorway`
- `space`
- `none`
- `unknown`

Allowed `body_language` values:

- `lip_licking`
- `yawning`
- `whale_eye`
- `turning_away`
- `avoidance`
- `frozen`
- `stiff_body`
- `play_bow`
- `loose_body`
- `tucked_tail`
- `high_tail`
- `hackles_raised`
- `panting`
- `displacement_sniffing`
- `blocking`
- `hovering`
- `muzzle_punch`
- `air_snap`
- `unknown`

Allowed `vocalization` values:

- `silent`
- `growl`
- `bark`
- `high_pitched_bark`
- `whine`
- `snarl`
- `yelp`
- `unknown`

Allowed `posture` values:

- `cowered`
- `upright`
- `frozen`
- `loose`
- `stiff`
- `leaning_forward`
- `leaning_away`
- `unknown`

Allowed `movement` values:

- `approach`
- `retreat`
- `turning_away`
- `following`
- `chasing`
- `blocking`
- `circling`
- `still`
- `avoidant`
- `unknown`

Allowed `handler_intervention.type` values:

- `increased_distance`
- `removed_resource`
- `separated_dogs`
- `redirected_attention`
- `ended_play`
- `leashed_dog`
- `none`
- `unknown`

Allowed `handler_intervention.result` values:

- `deescalated`
- `unchanged`
- `escalated`
- `unknown`

---

## 9. Derived Patterns

```json
{
  "derived_patterns": [
    {
      "pattern_id": "pattern_001",
      "time_window": "last_24_hours",
      "metric": "social_stress_frequency",
      "baseline_value": "rare",
      "observed_value": "three_events",
      "deviation": "above_baseline",
      "risk_impact": "moderate",
      "logic": "Multiple stress signals occurred around the same large dog and high-value resources.",
      "source_observation_ids": [
        "obs_001",
        "obs_002",
        "obs_003"
      ]
    }
  ]
}
```

Allowed `deviation` values:

- `below_baseline`
- `at_baseline`
- `above_baseline`
- `new_behavior`
- `unknown`

Allowed `risk_impact` values:

- `none`
- `low`
- `moderate`
- `high`
- `unknown`

---

## 10. Risk Assessment

```json
{
  "risk_assessment": {
    "risk_level": 6,
    "risk_band": "moderate",
    "primary_risk_domain": "behavior",
    "risk_factors": [
      "stress signals near high-value resource",
      "large dog proximity",
      "freezing and stiff body"
    ],
    "protective_factors": [
      "deescalated when distance increased",
      "no bite or injury reported"
    ],
    "missing_information": [
      "whether this dog has guarded chews before",
      "whether the other dog continued approaching"
    ],
    "recommended_action": "manage_environment_and_monitor",
    "escalation_conditions": [
      "growling or snapping increases",
      "dog cannot relax after separation",
      "resource guarding repeats",
      "physical injury occurs"
    ],
    "logic": "The event includes subtle and overt stress signals around a resource. Conservative management is appropriate even without physical injury.",
    "source_guideline_ids": [
      "GL_SOCIAL_STRESS_001",
      "GL_RESOURCE_GUARDING_001"
    ]
  }
}
```

Allowed `risk_band` values:

- `low`
- `moderate`
- `high`
- `urgent`

Allowed `primary_risk_domain` values:

- `health`
- `behavior`
- `social`
- `environment`
- `mixed`
- `unknown`

`risk_level` is an integer from `1` to `10`.

---

## 11. Agent Outputs

Each agent must write a structured output before handoff.

```json
{
  "agent_outputs": [
    {
      "agent": "BehaviorAgent",
      "timestamp": "2026-05-08T09:21:00-07:00",
      "input_observation_ids": [
        "obs_001"
      ],
      "conclusion": "moderate social stress",
      "confidence": 0.84,
      "reasoning_trace": "Lip licking, freezing, and stiff body near a chew suggest stress around a valued resource.",
      "recommended_state_updates": [
        {
          "path": "risk_assessment.primary_risk_domain",
          "value": "social"
        }
      ],
      "source_guideline_ids": [
        "GL_SOCIAL_STRESS_001",
        "GL_RESOURCE_GUARDING_001"
      ]
    }
  ]
}
```

Required fields:

- `agent`
- `timestamp`
- `input_observation_ids`
- `conclusion`
- `confidence`
- `reasoning_trace`
- `source_guideline_ids`

The `reasoning_trace` must be concise and must not contain unsupported diagnosis.

---

## 12. Handoff Package

The handoff package is the state subset passed between agents.

```json
{
  "handoff": {
    "from_agent": "BehaviorAgent",
    "to_agent": "CareCoordinator",
    "dog_id": "dog_123",
    "workflow_id": "wf_20260508_001",
    "current_observations": [
      "obs_001"
    ],
    "conflicting_signals": [
      {
        "signal": "freezing_near_chew",
        "behavior_interpretation": "stress or resource concern",
        "health_interpretation": "no physical symptom indicated",
        "requires_resolution": true
      }
    ],
    "agent_reasoning_trace": [
      {
        "agent": "BehaviorAgent",
        "conclusion": "moderate social stress",
        "reasoning": "Stress signals appeared in a resource-proximity context.",
        "source_guideline_ids": [
          "GL_SOCIAL_STRESS_001"
        ]
      }
    ],
    "source_guideline_ids": [
      "GL_SOCIAL_STRESS_001",
      "GL_RESOURCE_GUARDING_001"
    ]
  }
}
```

Handoff must include:

- `current_observations`
- `conflicting_signals`
- `agent_reasoning_trace`
- `source_guideline_ids`

---

## 13. Safety Review

```json
{
  "safety_review": {
    "safety_checked": true,
    "checked_at": "2026-05-08T09:24:00-07:00",
    "blocked_content": [],
    "rewrites_applied": [
      {
        "original": "This is harmless.",
        "replacement": "This does not currently include reported injury, but continued monitoring is appropriate."
      }
    ],
    "diagnosis_present": false,
    "medication_advice_present": false,
    "over_reassurance_present": false,
    "source_guideline_ids_present": true,
    "final_status": "approved"
  }
}
```

Allowed `final_status` values:

- `approved`
- `approved_with_rewrites`
- `blocked_needs_human_review`

---

## 14. Final Recommendation

```json
{
  "final_recommendation": {
    "risk_level": 6,
    "risk_band": "moderate",
    "summary": "Mochi showed stress signals when a larger dog approached her chew.",
    "recommendation": "Increase distance between dogs around high-value items, remove the chew during shared time, and continue monitoring body language.",
    "owner_message": "Quick update: Mochi became tense when another dog came near her chew. I separated them calmly, removed the chew from shared space, and she settled after more distance. I will keep monitoring and avoid shared high-value items.",
    "escalation_conditions": [
      "growling, snapping, or lunging increases",
      "either dog cannot relax after separation",
      "resource guarding repeats",
      "any injury occurs"
    ],
    "safety_checked": true,
    "source_guideline_ids": [
      "GL_SOCIAL_STRESS_001",
      "GL_RESOURCE_GUARDING_001"
    ]
  }
}
```

Final recommendations must not be emitted unless:

- `safety_review.safety_checked` is `true`
- `safety_review.final_status` is `approved` or `approved_with_rewrites`
- `source_guideline_ids` is non-empty
- diagnosis and medication advice are absent

---

## 15. Minimal Complete Example

```json
{
  "schema_version": "0.1.0",
  "workflow_id": "wf_20260508_001",
  "dog_id": "dog_123",
  "dog_profile": {
    "id": "dog_123",
    "name": "Mochi",
    "breed": "Shiba Inu"
  },
  "behavioral_baseline": {
    "general_temperament": "food_motivated",
    "social_profile": {
      "large_dog_reaction": "neutral",
      "small_dog_reaction": "friendly",
      "prey_drive_level": 4,
      "known_triggers": [
        "fast_movements",
        "direct_staring"
      ],
      "stress_signals_typical": [
        "lip_licking"
      ]
    },
    "resource_guarding_profile": {
      "food_guarding": "none_known",
      "toy_guarding": "mild",
      "space_guarding": "none_known",
      "human_guarding": "unknown",
      "known_guarded_resources": [
        "high_value_chews"
      ]
    }
  },
  "health_baseline": {
    "normal_appetite": "high",
    "normal_stool_quality": "firm",
    "normal_activity_level": "medium"
  },
  "current_session_state": {
    "is_active": true,
    "last_interaction_timestamp": "2026-05-08T09:20:00-07:00",
    "pending_conflicts": []
  },
  "active_context": {
    "target_agent": "BehaviorAgent",
    "task": "Assess whether the social observation indicates stress, resource concern, or normal play.",
    "current_observation_ids": [
      "obs_001"
    ],
    "allowed_guideline_ids": [
      "GL_SOCIAL_STRESS_001",
      "GL_RESOURCE_GUARDING_001"
    ],
    "required_output_path": "agent_outputs"
  },
  "observations": [
    {
      "observation_id": "obs_001",
      "timestamp": "2026-05-08T09:15:00-07:00",
      "source": "user_log",
      "category": "social_interaction",
      "raw_text": "Mochi froze and licked her lips when the large dog came near her chew.",
      "confidence": 0.91,
      "entity_involved": {
        "type": "large_dog",
        "id": "dog_456",
        "relative_size": "larger"
      },
      "social_context": {
        "interaction_type": "resource_proximity",
        "initiator": "other_dog",
        "distance": "near",
        "resource_involved": {
          "present": true,
          "type": "chew",
          "ownership": "primary_dog"
        },
        "signals": {
          "body_language": [
            "lip_licking",
            "frozen",
            "stiff_body"
          ],
          "vocalization": [
            "silent"
          ],
          "posture": "frozen",
          "movement": "avoidant"
        },
        "handler_intervention": {
          "occurred": true,
          "type": "increased_distance",
          "result": "deescalated"
        }
      },
      "health_context": null,
      "severity_score": 6,
      "source_guideline_ids": [
        "GL_SOCIAL_STRESS_001",
        "GL_RESOURCE_GUARDING_001"
      ]
    }
  ],
  "derived_patterns": [],
  "risk_assessment": {
    "risk_level": 6,
    "risk_band": "moderate",
    "primary_risk_domain": "social",
    "risk_factors": [
      "stress signals near high-value resource",
      "large dog proximity"
    ],
    "protective_factors": [
      "deescalated when distance increased"
    ],
    "missing_information": [
      "whether this dog has guarded chews before"
    ],
    "recommended_action": "manage_environment_and_monitor",
    "escalation_conditions": [
      "growling or snapping increases",
      "resource guarding repeats",
      "physical injury occurs"
    ],
    "logic": "Stress signals appeared during resource proximity. Management and monitoring are appropriate.",
    "source_guideline_ids": [
      "GL_SOCIAL_STRESS_001",
      "GL_RESOURCE_GUARDING_001"
    ]
  },
  "agent_outputs": [],
  "handoff": {
    "current_observations": [
      "obs_001"
    ],
    "conflicting_signals": [],
    "agent_reasoning_trace": [],
    "source_guideline_ids": [
      "GL_SOCIAL_STRESS_001",
      "GL_RESOURCE_GUARDING_001"
    ]
  },
  "safety_review": {
    "safety_checked": true,
    "diagnosis_present": false,
    "medication_advice_present": false,
    "over_reassurance_present": false,
    "source_guideline_ids_present": true,
    "final_status": "approved"
  },
  "final_recommendation": {
    "risk_level": 6,
    "risk_band": "moderate",
    "summary": "Mochi showed stress signals when a larger dog approached her chew.",
    "recommendation": "Increase distance between dogs around high-value items, remove the chew during shared time, and continue monitoring body language.",
    "safety_checked": true,
    "source_guideline_ids": [
      "GL_SOCIAL_STRESS_001",
      "GL_RESOURCE_GUARDING_001"
    ]
  }
}
```

---

## 16. Implementation Rules

Before implementing or modifying an agent:

1. Confirm which fields it reads.
2. Confirm which fields it writes.
3. Confirm which fields it must never overwrite.
4. Add or update edge cases in `docs/test_cases.md`.
5. Ensure all safety-relevant outputs include `source_guideline_ids`.

Agent ownership:

| Component | Reads | Writes |
| --- | --- | --- |
| `LogExtractor` | raw user input | `observations` |
| `ContextHydrator` | `dog_id` | `dog_profile`, `behavioral_baseline`, `health_baseline` |
| `PatternAnalyzer` | `observations`, baselines | `derived_patterns` |
| `HealthAgent` | `observations`, `health_baseline`, guidelines | `agent_outputs`, health risk suggestions |
| `BehaviorAgent` | `observations`, `behavioral_baseline`, guidelines | `agent_outputs`, social/behavior risk suggestions |
| `RiskEvaluator` | observations, patterns, agent outputs | `risk_assessment` |
| `CareCoordinator` | all state | `current_session_state`, `handoff`, conflict resolution |
| `SafetyAgent` | recommendation candidate | `safety_review` |
| `CommunicationAgent` | safety-approved recommendation | `final_recommendation` |

No component may erase another component's output without writing a new state update explaining why.
