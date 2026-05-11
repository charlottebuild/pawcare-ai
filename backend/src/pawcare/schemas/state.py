from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class BodyLanguageSignal(str, Enum):
    # Shared / dog-focused signals from docs/state_schema.md.
    lip_licking = "lip_licking"
    yawning = "yawning"
    whale_eye = "whale_eye"
    turning_away = "turning_away"
    avoidance = "avoidance"
    frozen = "frozen"
    stiff_body = "stiff_body"
    play_bow = "play_bow"
    loose_body = "loose_body"
    tucked_tail = "tucked_tail"
    high_tail = "high_tail"
    hackles_raised = "hackles_raised"
    panting = "panting"
    displacement_sniffing = "displacement_sniffing"
    blocking = "blocking"
    hovering = "hovering"
    muzzle_punch = "muzzle_punch"
    air_snap = "air_snap"
    lowered_tail = "lowered_tail"
    tail_tucked = "tail_tucked"
    tail_wagging_loose = "tail_wagging_loose"
    tail_wagging_stiff = "tail_wagging_stiff"
    ears_back = "ears_back"
    ears_forward = "ears_forward"
    crouching = "crouching"
    rolling_over = "rolling_over"
    showing_belly = "showing_belly"
    raised_paw = "raised_paw"
    shaking_off = "shaking_off"
    scratching = "scratching"
    # Cat-specific signals. These are valid only when the observation species is cat.
    puffed_tail = "puffed_tail"
    arched_back = "arched_back"
    flattened_ears = "flattened_ears"
    slow_blink = "slow_blink"
    hiding = "hiding"
    hissing = "hissing"
    swatting = "swatting"
    unknown = "unknown"


class VocalizationSignal(str, Enum):
    silent = "silent"
    growl = "growl"
    bark = "bark"
    high_pitched_bark = "high_pitched_bark"
    whine = "whine"
    snarl = "snarl"
    yelp = "yelp"
    unknown = "unknown"


class ObservationCategory(str, Enum):
    food_intake = "food_intake"
    water_intake = "water_intake"
    stool = "stool"
    urination = "urination"
    vomiting = "vomiting"
    energy = "energy"
    mobility = "mobility"
    sleep = "sleep"
    social_interaction = "social_interaction"
    environment_change = "environment_change"
    owner_instruction = "owner_instruction"
    medication_note = "medication_note"
    other = "other"


class InteractionType(str, Enum):
    greeting = "greeting"
    parallel_presence = "parallel_presence"
    play = "play"
    resource_proximity = "resource_proximity"
    resource_conflict = "resource_conflict"
    doorway_or_threshold = "doorway_or_threshold"
    human_attention = "human_attention"
    walk_passing = "walk_passing"
    chase = "chase"
    staring = "staring"
    unknown = "unknown"


class Initiator(str, Enum):
    primary_dog = "primary_dog"
    other_dog = "other_dog"
    human = "human"
    unclear = "unclear"


class InteractionDistance(str, Enum):
    across_room = "across_room"
    same_room = "same_room"
    near = "near"
    direct_contact = "direct_contact"
    blocked_access = "blocked_access"
    unknown = "unknown"


class ResourceType(str, Enum):
    food = "food"
    treat = "treat"
    chew = "chew"
    toy = "toy"
    bed = "bed"
    crate = "crate"
    water_bowl = "water_bowl"
    human_attention = "human_attention"
    doorway = "doorway"
    space = "space"
    none = "none"
    unknown = "unknown"


class Posture(str, Enum):
    cowered = "cowered"
    upright = "upright"
    frozen = "frozen"
    loose = "loose"
    stiff = "stiff"
    leaning_forward = "leaning_forward"
    leaning_away = "leaning_away"
    unknown = "unknown"


class Movement(str, Enum):
    approach = "approach"
    retreat = "retreat"
    turning_away = "turning_away"
    following = "following"
    chasing = "chasing"
    blocking = "blocking"
    circling = "circling"
    still = "still"
    avoidant = "avoidant"
    unknown = "unknown"


class HandlerInterventionType(str, Enum):
    increased_distance = "increased_distance"
    removed_resource = "removed_resource"
    separated_dogs = "separated_dogs"
    redirected_attention = "redirected_attention"
    ended_play = "ended_play"
    leashed_dog = "leashed_dog"
    none = "none"
    unknown = "unknown"


class HandlerInterventionResult(str, Enum):
    deescalated = "deescalated"
    unchanged = "unchanged"
    escalated = "escalated"
    unknown = "unknown"


class RiskBand(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"
    urgent = "urgent"


class RiskDomain(str, Enum):
    health = "health"
    behavior = "behavior"
    social = "social"
    environment = "environment"
    mixed = "mixed"
    unknown = "unknown"


class SafetyFinalStatus(str, Enum):
    approved = "approved"
    approved_with_rewrites = "approved_with_rewrites"
    blocked_needs_human_review = "blocked_needs_human_review"


class UserResponseStatus(str, Enum):
    updated = "updated"
    attention_needed = "attention_needed"
    escalate = "escalate"
    needs_review = "needs_review"


class PendingConflictType(str, Enum):
    behavior_vs_health = "behavior_vs_health"
    risk_level_disagreement = "risk_level_disagreement"
    baseline_conflict = "baseline_conflict"
    guideline_conflict = "guideline_conflict"
    owner_instruction_vs_safety = "owner_instruction_vs_safety"
    missing_information = "missing_information"


class RelativeSize(str, Enum):
    smaller = "smaller"
    same_size = "same_size"
    larger = "larger"
    unknown = "unknown"


class EntityType(str, Enum):
    large_dog = "large_dog"
    small_dog = "small_dog"
    dog = "dog"
    human = "human"
    unknown = "unknown"


class Species(str, Enum):
    dog = "dog"
    cat = "cat"
    other = "other"
    unknown = "unknown"


class Source(str, Enum):
    user_log = "user_log"
    scheduled_scan = "scheduled_scan"
    sensor = "sensor"
    owner_instruction = "owner_instruction"
    agent_verified_history = "agent_verified_history"


class OwnerContactPreferences(StrictBaseModel):
    notify_for_moderate_risk: bool = True
    preferred_channel: str | None = None
    tone_preference: str | None = None


class DogProfile(StrictBaseModel):
    id: str
    species: Species = Species.dog
    name: str | None = None
    breed: str | None = None
    age_years: float | None = Field(default=None, ge=0)
    weight_kg: float | None = Field(default=None, ge=0)
    sex: str | None = None
    spayed_neutered: bool | None = None
    owner_contact_preferences: OwnerContactPreferences | None = None
    care_notes: list[str] = Field(default_factory=list)


class SocialProfile(StrictBaseModel):
    large_dog_reaction: str = "unknown"
    small_dog_reaction: str = "unknown"
    human_reaction: str = "unknown"
    prey_drive_level: int | None = Field(default=None, ge=1, le=10)
    play_style: str | None = None
    known_triggers: list[str] = Field(default_factory=list)
    stress_signals_typical: list[BodyLanguageSignal] = Field(default_factory=list)
    recovery_pattern: str | None = None


class ResourceGuardingProfile(StrictBaseModel):
    food_guarding: str = "unknown"
    toy_guarding: str = "unknown"
    space_guarding: str = "unknown"
    human_guarding: str = "unknown"
    known_guarded_resources: list[str] = Field(default_factory=list)


class BehavioralBaseline(StrictBaseModel):
    general_temperament: str = "unknown"
    energy_level: str = "unknown"
    confidence_level: str = "unknown"
    separation_comfort: str | None = None
    social_profile: SocialProfile = Field(default_factory=SocialProfile)
    resource_guarding_profile: ResourceGuardingProfile = Field(
        default_factory=ResourceGuardingProfile
    )


class HealthBaseline(StrictBaseModel):
    normal_appetite: str = "unknown"
    normal_stool_quality: str = "unknown"
    normal_stool_frequency_per_day: int | None = Field(default=None, ge=0)
    normal_water_intake: str = "unknown"
    normal_activity_level: str = "unknown"
    known_medical_notes: list[str] = Field(default_factory=list)
    owner_escalation_rules: list[str] = Field(default_factory=list)


class EnvironmentContext(StrictBaseModel):
    location_type: str | None = None
    new_environment: bool | None = None
    other_animals_present: bool | None = None
    other_dog_ids: list[str] = Field(default_factory=list)
    notable_context: list[str] = Field(default_factory=list)


class PendingConflict(StrictBaseModel):
    conflict_id: str
    type: PendingConflictType
    description: str
    involved_agents: list[str] = Field(default_factory=list)
    resolved: bool = False
    resolution: str | None = None


class CurrentSessionState(StrictBaseModel):
    is_active: bool = True
    session_started_at: str | None = None
    last_interaction_timestamp: str | None = None
    environment: EnvironmentContext | None = None
    pending_conflicts: list[PendingConflict] = Field(default_factory=list)


class PriorAgentSummary(StrictBaseModel):
    agent: str
    conclusion: str
    risk_band: str | None = None


class ActiveContext(StrictBaseModel):
    target_agent: str
    task: str
    current_observation_ids: list[str] = Field(default_factory=list)
    relevant_baseline: dict[str, Any] = Field(default_factory=dict)
    prior_agent_summary: PriorAgentSummary | None = None
    allowed_guideline_ids: list[str] = Field(default_factory=list)
    required_output_path: str = "agent_outputs"
    must_answer: list[str] = Field(default_factory=list)


class EntityInvolved(StrictBaseModel):
    type: EntityType
    species: Species = Species.unknown
    id: str | None = None
    name: str | None = None
    relative_size: RelativeSize = RelativeSize.unknown


class ResourceInvolved(StrictBaseModel):
    present: bool = False
    type: ResourceType | None = None
    ownership: str | None = None


class SocialSignals(StrictBaseModel):
    body_language: list[BodyLanguageSignal] = Field(default_factory=list)
    vocalization: list[VocalizationSignal] = Field(default_factory=list)
    posture: Posture = Posture.unknown
    movement: Movement = Movement.unknown


class HandlerIntervention(StrictBaseModel):
    occurred: bool = False
    type: HandlerInterventionType | None = None
    result: HandlerInterventionResult | None = None


class SocialContext(StrictBaseModel):
    interaction_type: InteractionType
    initiator: Initiator = Initiator.unclear
    distance: InteractionDistance = InteractionDistance.unknown
    duration_seconds: int | None = Field(default=None, ge=0)
    resource_involved: ResourceInvolved = Field(default_factory=ResourceInvolved)
    signals: SocialSignals = Field(default_factory=SocialSignals)
    handler_intervention: HandlerIntervention = Field(
        default_factory=HandlerIntervention
    )


class Observation(StrictBaseModel):
    observation_id: str
    timestamp: str
    source: Source = Source.user_log
    category: ObservationCategory
    species: Species = Species.dog
    raw_text: str
    confidence: float = Field(ge=0, le=1)
    entity_involved: EntityInvolved | None = None
    social_context: SocialContext | None = None
    health_context: dict[str, Any] | None = None
    severity_score: int | None = Field(default=None, ge=1, le=10)
    source_guideline_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def social_context_required_for_social_interaction(self) -> Observation:
        if (
            self.category == ObservationCategory.social_interaction
            and self.social_context is None
        ):
            raise ValueError("social_context is required for social_interaction observations")
        if self.species == Species.dog and self.social_context is not None:
            cat_only_signals = {
                BodyLanguageSignal.puffed_tail.value,
                BodyLanguageSignal.arched_back.value,
                BodyLanguageSignal.flattened_ears.value,
                BodyLanguageSignal.slow_blink.value,
                BodyLanguageSignal.hiding.value,
                BodyLanguageSignal.hissing.value,
                BodyLanguageSignal.swatting.value,
            }
            observed_signals = set(self.social_context.signals.body_language)
            invalid_signals = sorted(observed_signals & cat_only_signals)
            if invalid_signals:
                raise ValueError(
                    "cat-only body_language values are not valid for dog observations: "
                    + ", ".join(invalid_signals)
                )
        return self


class DerivedPattern(StrictBaseModel):
    pattern_id: str
    time_window: str
    metric: str
    baseline_value: str | None = None
    observed_value: str | None = None
    deviation: str
    risk_impact: str
    logic: str
    source_observation_ids: list[str] = Field(default_factory=list)


class RiskAssessment(StrictBaseModel):
    risk_level: int = Field(ge=1, le=10)
    risk_band: RiskBand
    primary_risk_domain: RiskDomain = RiskDomain.unknown
    risk_factors: list[str] = Field(default_factory=list)
    protective_factors: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    recommended_action: str
    escalation_conditions: list[str] = Field(default_factory=list)
    logic: str
    source_guideline_ids: list[str] = Field(default_factory=list, min_length=1)


class ProposedUpdate(StrictBaseModel):
    target_path: str
    operation: Literal["append", "set", "merge", "remove"]
    value: Any


class AgentOutput(StrictBaseModel):
    agent: str
    timestamp: str | None = None
    input_active_context_id: str | None = None
    input_observation_ids: list[str] = Field(default_factory=list)
    conclusion: str
    confidence: float = Field(ge=0, le=1)
    missing_information: list[str] = Field(default_factory=list)
    proposed_update: ProposedUpdate | None = None
    proposed_updates: list[ProposedUpdate] = Field(default_factory=list)
    reasoning_trace: str
    source_guideline_ids: list[str] = Field(default_factory=list, min_length=1)


class ConflictingSignal(StrictBaseModel):
    signal: str
    behavior_interpretation: str | None = None
    health_interpretation: str | None = None
    requires_resolution: bool = False


class ReasoningTraceItem(StrictBaseModel):
    agent: str
    conclusion: str
    reasoning: str
    source_guideline_ids: list[str] = Field(default_factory=list)


class HandoffPackage(StrictBaseModel):
    from_agent: str | None = None
    to_agent: str | None = None
    dog_id: str | None = None
    workflow_id: str | None = None
    current_observations: list[str] = Field(default_factory=list)
    conflicting_signals: list[ConflictingSignal] = Field(default_factory=list)
    agent_reasoning_trace: list[ReasoningTraceItem] = Field(default_factory=list)
    source_guideline_ids: list[str] = Field(default_factory=list)


class SafetyRewrite(StrictBaseModel):
    original: str
    replacement: str


class SafetyReview(StrictBaseModel):
    safety_checked: bool
    checked_at: str | None = None
    blocked_content: list[str] = Field(default_factory=list)
    rewrites_applied: list[SafetyRewrite] = Field(default_factory=list)
    diagnosis_present: bool = False
    medication_advice_present: bool = False
    over_reassurance_present: bool = False
    source_guideline_ids_present: bool = False
    final_status: SafetyFinalStatus


class FinalRecommendation(StrictBaseModel):
    risk_level: int = Field(ge=1, le=10)
    risk_band: RiskBand
    summary: str
    recommendation: str | None = None
    owner_message: str | None = None
    escalation_conditions: list[str] = Field(default_factory=list)
    safety_checked: bool
    source_guideline_ids: list[str] = Field(default_factory=list, min_length=1)


class PawCareState(StrictBaseModel):
    schema_version: str = "0.1.0"
    workflow_id: str
    dog_id: str
    dog_profile: DogProfile
    behavioral_baseline: BehavioralBaseline
    health_baseline: HealthBaseline
    current_session_state: CurrentSessionState
    active_context: ActiveContext | None = None
    observations: list[Observation] = Field(default_factory=list)
    derived_patterns: list[DerivedPattern] = Field(default_factory=list)
    risk_assessment: RiskAssessment | None = None
    agent_outputs: list[AgentOutput] = Field(default_factory=list)
    handoff: HandoffPackage | None = None
    safety_review: SafetyReview | None = None
    final_recommendation: FinalRecommendation | None = None


class UserResponse(StrictBaseModel):
    status: UserResponseStatus
    workflow_id: str
    dog_id: str
    risk_band: RiskBand | None = None
    message: str
    escalation_conditions: list[str] = Field(default_factory=list)
    source_guideline_ids: list[str] = Field(default_factory=list)
