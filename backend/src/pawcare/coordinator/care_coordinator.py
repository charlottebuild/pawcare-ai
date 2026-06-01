from __future__ import annotations

from dataclasses import dataclass

from pawcare.agents import BehaviorAgent, CommunicationAgent, HealthAgent, SafetyAgent
from pawcare.schemas.state import (
    ActiveContext,
    AgentOutput,
    BehavioralBaseline,
    CurrentSessionState,
    DogProfile,
    FinalRecommendation,
    HealthBaseline,
    OwnerContactPreferences,
    PawCareState,
    PendingConflict,
    PendingConflictType,
    ProposedUpdate,
    RiskAssessment,
    RiskBand,
    RiskDomain,
    Species,
)
from pawcare.services.behavior_reference_service import BehaviorReferenceService
from pawcare.services.pet_models import PetRecord
from pawcare.services.professional_reference_service import ProfessionalReferenceService
from pawcare.skills import LogExtractor

HEALTH_OBSERVATION_CATEGORIES = {
    "food_intake",
    "stool",
    "urination",
    "vomiting",
    "energy",
    "mobility",
    "medication_note",
}


@dataclass(frozen=True)
class CoordinatorResult:
    state: PawCareState
    accepted_updates: list[ProposedUpdate]
    rejected_updates: list[ProposedUpdate]


class CareCoordinator:
    """First-pass orchestrator for the PawCare workflow.

    The Coordinator owns the global state. Worker agents return proposed updates;
    this class validates and merges only the supported updates.
    """

    def __init__(
        self,
        *,
        log_extractor: LogExtractor | None = None,
        behavior_agent: BehaviorAgent | None = None,
        health_agent: HealthAgent | None = None,
        safety_agent: SafetyAgent | None = None,
        communication_agent: CommunicationAgent | None = None,
        professional_reference_service: ProfessionalReferenceService | None = None,
        behavior_reference_service: BehaviorReferenceService | None = None,
    ) -> None:
        self.log_extractor = log_extractor or LogExtractor()
        self.behavior_agent = behavior_agent or BehaviorAgent()
        self.health_agent = health_agent or HealthAgent()
        self.safety_agent = safety_agent or SafetyAgent()
        self.communication_agent = communication_agent or CommunicationAgent()
        self.professional_reference_service = (
            professional_reference_service or ProfessionalReferenceService()
        )
        self.behavior_reference_service = (
            behavior_reference_service or BehaviorReferenceService()
        )

    def handle_log(
        self,
        *,
        workflow_id: str,
        dog_id: str,
        raw_text: str,
        timestamp: str,
        dog_profile: DogProfile,
        behavioral_baseline: BehavioralBaseline,
        health_baseline: HealthBaseline,
        species: Species = Species.dog,
    ) -> CoordinatorResult:
        batch = self.log_extractor.extract(
            dog_id=dog_id,
            raw_text=raw_text,
            timestamp=timestamp,
            species=species,
        )

        state = PawCareState(
            workflow_id=workflow_id,
            dog_id=dog_id,
            dog_profile=dog_profile,
            behavioral_baseline=behavioral_baseline,
            health_baseline=health_baseline,
            current_session_state=CurrentSessionState(
                is_active=True,
                last_interaction_timestamp=timestamp,
            ),
            observations=batch.observations,
        )

        accepted_updates: list[ProposedUpdate] = []
        rejected_updates: list[ProposedUpdate] = []

        for active_context, output in self._run_worker_agents(state=state):
            state.active_context = active_context
            state.agent_outputs.append(output)
            if output.proposed_update is not None:
                if self._merge_update(
                    state=state,
                    output=output,
                    update=output.proposed_update,
                ):
                    accepted_updates.append(output.proposed_update)
                else:
                    rejected_updates.append(output.proposed_update)

        if state.risk_assessment is not None:
            candidate = self._build_recommendation_candidate(state=state)
            safety_review = self.safety_agent.review_recommendation(candidate)
            state.safety_review = safety_review
            if safety_review.final_status != "blocked_needs_human_review":
                state.final_recommendation = self.communication_agent.format_owner_message(
                    risk_assessment=state.risk_assessment,
                    safety_review=safety_review,
                    owner_preferences=self._owner_preferences(state),
                )

        return CoordinatorResult(
            state=state,
            accepted_updates=accepted_updates,
            rejected_updates=rejected_updates,
        )

    def _run_worker_agents(self, *, state: PawCareState) -> list[tuple[ActiveContext, AgentOutput]]:
        results: list[tuple[ActiveContext, AgentOutput]] = []

        health_context = self._build_health_active_context(state=state)
        if health_context.current_observation_ids:
            health_output = self.health_agent.analyze(
                active_context=health_context,
                observations=[
                    observation
                    for observation in state.observations
                    if observation.observation_id in health_context.current_observation_ids
                ],
            )
            results.append((health_context, health_output))

        behavior_context = self._build_behavior_active_context(state=state)
        if behavior_context.current_observation_ids:
            behavior_output = self.behavior_agent.analyze(
                active_context=behavior_context,
                observations=[
                    observation
                    for observation in state.observations
                    if observation.observation_id in behavior_context.current_observation_ids
                ],
            )
            results.append((behavior_context, behavior_output))
        return results

    def _build_health_active_context(self, *, state: PawCareState) -> ActiveContext:
        health_observation_ids = [
            observation.observation_id
            for observation in state.observations
            if observation.category in HEALTH_OBSERVATION_CATEGORIES
            or (observation.health_context or {}).get("condition_triage")
        ]

        return ActiveContext(
            target_agent="HealthAgent",
            task="Assess whether the current health observations indicate monitoring, owner notification, or escalation needs.",
            current_observation_ids=health_observation_ids,
            relevant_baseline={
                "health_baseline": state.health_baseline.model_dump(),
                "medical_notes": state.dog_profile.care_notes,
                "professional_references": self._professional_reference_payload(
                    state=state
                ),
            },
            allowed_guideline_ids=[
                "GL_STOOL_001",
                "GL_APPETITE_002",
                "GL_VOMITING_001",
                "GL_LETHARGY_001",
                "GL_LAMENESS_001",
                "GL_NSAID_SIDE_EFFECT_001",
                "GL_ACL_POSTOP_001",
                "GL_CONDITION_GI_001",
                "GL_CONDITION_ORAL_NECK_001",
                "GL_CONDITION_MOBILITY_001",
                "GL_CONDITION_SKIN_LUMP_001",
                "GL_CONDITION_URINARY_001",
                "GL_CONDITION_RESPIRATORY_001",
            ],
            required_output_path="agent_outputs",
            must_answer=[
                "Which health signals are present?",
                "Which guideline IDs ground the concern?",
                "What information is missing?",
            ],
        )

    def _build_behavior_active_context(self, *, state: PawCareState) -> ActiveContext:
        social_observation_ids = [
            observation.observation_id
            for observation in state.observations
            if observation.category == "social_interaction"
        ]

        return ActiveContext(
            target_agent="BehaviorAgent",
            task="Assess whether the current observations indicate social stress, resource concern, or appropriate play.",
            current_observation_ids=social_observation_ids,
            relevant_baseline={
                "social_profile": state.behavioral_baseline.social_profile.model_dump(),
                "resource_guarding_profile": state.behavioral_baseline.resource_guarding_profile.model_dump(),
                "behavior_references": self._behavior_reference_payload(state=state),
            },
            allowed_guideline_ids=[
                "GL_SOCIAL_STRESS_001",
                "GL_RESOURCE_GUARDING_001",
                "GL_SOCIAL_PLAY_001",
            ],
            required_output_path="agent_outputs",
            must_answer=[
                "Does this interaction include stress signals?",
                "Is a resource involved?",
                "What information is missing?",
            ],
        )

    def _professional_reference_payload(self, *, state: PawCareState) -> list[dict[str, object]]:
        raw_text = " ".join(observation.raw_text for observation in state.observations)
        matches = self.professional_reference_service.find_matches(
            raw_text=raw_text,
            pet=PetRecord(
                pet_id=state.dog_id,
                user_id="_coordinator",
                dog_profile=state.dog_profile,
                behavioral_baseline=state.behavioral_baseline,
                health_baseline=state.health_baseline,
                observations=list(state.observations),
            ),
            recent_observations=state.observations,
            limit=3,
        )
        return self.professional_reference_service.as_payload(matches)

    def _behavior_reference_payload(self, *, state: PawCareState) -> list[dict[str, object]]:
        matches = self.behavior_reference_service.find_matches(
            observations=state.observations,
            limit=3,
        )
        return self.behavior_reference_service.as_payload(matches)

    def _merge_update(
        self,
        *,
        state: PawCareState,
        output: AgentOutput,
        update: ProposedUpdate,
    ) -> bool:
        if update.operation != "append":
            return False

        if update.target_path == "risk_assessment.risk_factors":
            risk = self._ensure_risk_assessment(state=state, output=output)
            risk.risk_factors.append(str(update.value))
            return True

        if update.target_path == "risk_assessment.protective_factors":
            risk = self._ensure_risk_assessment(state=state, output=output)
            risk.protective_factors.append(str(update.value))
            return True

        if update.target_path == "current_session_state.pending_conflicts":
            value = update.value if isinstance(update.value, dict) else {}
            state.current_session_state.pending_conflicts.append(
                PendingConflict(
                    conflict_id=f"conflict_{len(state.current_session_state.pending_conflicts) + 1:03d}",
                    type=PendingConflictType(value.get("type", "missing_information")),
                    description=value.get(
                        "description",
                        "Worker proposed a conflict or missing-information note.",
                    ),
                    involved_agents=[output.agent],
                    resolved=False,
                )
            )
            return True

        return False

    def _ensure_risk_assessment(
        self, *, state: PawCareState, output: AgentOutput
    ) -> RiskAssessment:
        if state.risk_assessment is None:
            state.risk_assessment = RiskAssessment(
                risk_level=self._risk_level_from_agent_output(output),
                risk_band=self._risk_band_from_agent_output(output),
                primary_risk_domain=self._risk_domain_from_agent_output(output),
                risk_factors=[],
                protective_factors=[],
                missing_information=list(output.missing_information),
                recommended_action=self._recommended_action_from_agent_output(output),
                escalation_conditions=self._escalation_conditions_from_agent_output(output),
                logic=output.reasoning_trace,
                source_guideline_ids=list(output.source_guideline_ids),
            )
        else:
            new_risk_level = self._risk_level_from_agent_output(output)
            if new_risk_level > state.risk_assessment.risk_level:
                state.risk_assessment.risk_level = new_risk_level
                state.risk_assessment.risk_band = self._risk_band_from_agent_output(output)
                state.risk_assessment.recommended_action = (
                    self._recommended_action_from_agent_output(output)
                )
                state.risk_assessment.escalation_conditions = (
                    self._escalation_conditions_from_agent_output(output)
                )

            output_domain = self._risk_domain_from_agent_output(output)
            if state.risk_assessment.primary_risk_domain != output_domain:
                if not any(
                    conflict.type == PendingConflictType.behavior_vs_health
                    for conflict in state.current_session_state.pending_conflicts
                ):
                    state.current_session_state.pending_conflicts.append(
                        PendingConflict(
                            conflict_id=(
                                f"conflict_{len(state.current_session_state.pending_conflicts) + 1:03d}"
                            ),
                            type=PendingConflictType.behavior_vs_health,
                            description=(
                                "Health and behavior observations both contributed to this risk assessment."
                            ),
                            involved_agents=["HealthAgent", "BehaviorAgent"],
                            resolved=False,
                        )
                    )
                state.risk_assessment.primary_risk_domain = RiskDomain.mixed

            for item in output.missing_information:
                if item not in state.risk_assessment.missing_information:
                    state.risk_assessment.missing_information.append(item)
            for guideline_id in output.source_guideline_ids:
                if guideline_id not in state.risk_assessment.source_guideline_ids:
                    state.risk_assessment.source_guideline_ids.append(guideline_id)
            if output.reasoning_trace not in state.risk_assessment.logic:
                state.risk_assessment.logic = (
                    state.risk_assessment.logic + " " + output.reasoning_trace
                )
        return state.risk_assessment

    def _risk_level_from_agent_output(self, output: AgentOutput) -> int:
        conclusion = output.conclusion.lower()
        if "high" in conclusion:
            return 8
        if "moderate" in conclusion:
            return 6
        if "play" in conclusion:
            return 2
        return 4

    def _risk_band_from_agent_output(self, output: AgentOutput) -> RiskBand:
        conclusion = output.conclusion.lower()
        if "high" in conclusion:
            return RiskBand.high
        if "moderate" in conclusion:
            return RiskBand.moderate
        return RiskBand.low

    def _risk_domain_from_agent_output(self, output: AgentOutput) -> RiskDomain:
        if output.agent == "HealthAgent":
            return RiskDomain.health
        return RiskDomain.social

    def _recommended_action_from_agent_output(self, output: AgentOutput) -> str:
        conclusion = output.conclusion.lower()
        if output.agent == "HealthAgent":
            if "high" in conclusion:
                return "notify_owner_and_seek_veterinary_guidance"
            if "moderate" in conclusion:
                return "notify_owner_and_monitor_health_signs"
            return "continue_health_monitoring"

        if "high" in conclusion:
            return "separate_and_notify_owner"
        if "resource" in conclusion:
            return "manage_environment_and_monitor"
        if "play" in conclusion:
            return "continue_monitoring"
        return "monitor_and_collect_more_information"

    def _escalation_conditions_from_agent_output(self, output: AgentOutput) -> list[str]:
        if output.agent == "HealthAgent":
            guideline_ids = set(output.source_guideline_ids)
            if "GL_CONDITION_RESPIRATORY_001" in guideline_ids:
                return [
                    "breathing becomes labored or difficult",
                    "gums look blue or pale",
                    "collapse or severe weakness appears",
                    "coughing or breathing effort worsens",
                ]
            if "GL_CONDITION_URINARY_001" in guideline_ids:
                return [
                    "the pet cannot urinate",
                    "the pet repeatedly strains with little or no urine",
                    "blood in urine appears or worsens",
                    "pain, vomiting, or low energy appears",
                ]
            if "GL_CONDITION_ORAL_NECK_001" in guideline_ids:
                return [
                    "swelling grows quickly",
                    "trouble swallowing, eating, or breathing appears",
                    "drooling, bleeding, severe pain, or low energy worsens",
                ]
            if "GL_CONDITION_SKIN_LUMP_001" in guideline_ids:
                return [
                    "the lump grows quickly",
                    "bleeding, discharge, pain, or heat appears",
                    "the pet seems unwell or very itchy",
                ]
            if "GL_CONDITION_GI_001" in guideline_ids:
                return [
                    "vomiting repeats or worsens",
                    "diarrhea becomes bloody or black/tarry",
                    "energy drops or the pet refuses food or water",
                    "signs continue or worsen",
                ]
            return [
                "vomiting repeats or worsens",
                "bloody or black/tarry stool appears",
                "energy drops below baseline",
                "the pet refuses food or water",
                "post-op mobility worsens or non-weight-bearing continues",
            ]

        return [
            "stress signals increase",
            "resource guarding repeats",
            "growling, snapping, or injury occurs",
            "the pet cannot relax after separation",
        ]

    def _build_recommendation_candidate(self, *, state: PawCareState) -> FinalRecommendation:
        risk = state.risk_assessment
        if risk is None:
            raise ValueError("risk_assessment is required before building a recommendation")

        summary = risk.logic
        recommendation = risk.recommended_action.replace("_", " ")
        owner_message = (
            f"Quick update: {summary} I am monitoring this and will follow the escalation conditions."
        )

        return FinalRecommendation(
            risk_level=risk.risk_level,
            risk_band=risk.risk_band,
            summary=summary,
            recommendation=recommendation,
            owner_message=owner_message,
            escalation_conditions=list(risk.escalation_conditions),
            safety_checked=True,
            source_guideline_ids=list(risk.source_guideline_ids),
        )

    def _owner_preferences(
        self, state: PawCareState
    ) -> OwnerContactPreferences | None:
        return state.dog_profile.owner_contact_preferences
