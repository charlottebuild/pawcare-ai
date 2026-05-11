from __future__ import annotations

from dataclasses import dataclass

from pawcare.agents import BehaviorAgent, CommunicationAgent, SafetyAgent
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
from pawcare.skills import LogExtractor


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
        safety_agent: SafetyAgent | None = None,
        communication_agent: CommunicationAgent | None = None,
    ) -> None:
        self.log_extractor = log_extractor or LogExtractor()
        self.behavior_agent = behavior_agent or BehaviorAgent()
        self.safety_agent = safety_agent or SafetyAgent()
        self.communication_agent = communication_agent or CommunicationAgent()

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

        active_context = self._build_behavior_active_context(state=state)
        state.active_context = active_context

        behavior_output = self.behavior_agent.analyze(
            active_context=active_context,
            observations=[
                observation
                for observation in state.observations
                if observation.observation_id in active_context.current_observation_ids
            ],
        )
        state.agent_outputs.append(behavior_output)

        accepted_updates: list[ProposedUpdate] = []
        rejected_updates: list[ProposedUpdate] = []
        if behavior_output.proposed_update is not None:
            if self._merge_update(
                state=state,
                output=behavior_output,
                update=behavior_output.proposed_update,
            ):
                accepted_updates.append(behavior_output.proposed_update)
            else:
                rejected_updates.append(behavior_output.proposed_update)

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

    def _build_behavior_active_context(self, *, state: PawCareState) -> ActiveContext:
        social_observation_ids = [
            observation.observation_id
            for observation in state.observations
            if observation.category == "social_interaction"
        ]
        observation_ids = social_observation_ids or [
            observation.observation_id for observation in state.observations
        ]

        return ActiveContext(
            target_agent="BehaviorAgent",
            task="Assess whether the current observations indicate social stress, resource concern, or appropriate play.",
            current_observation_ids=observation_ids,
            relevant_baseline={
                "social_profile": state.behavioral_baseline.social_profile.model_dump(),
                "resource_guarding_profile": state.behavioral_baseline.resource_guarding_profile.model_dump(),
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
                risk_level=self._risk_level_from_behavior_output(output),
                risk_band=self._risk_band_from_behavior_output(output),
                primary_risk_domain=RiskDomain.social,
                risk_factors=[],
                protective_factors=[],
                missing_information=list(output.missing_information),
                recommended_action=self._recommended_action_from_behavior_output(output),
                escalation_conditions=[
                    "stress signals increase",
                    "resource guarding repeats",
                    "growling, snapping, or injury occurs",
                    "the pet cannot relax after separation",
                ],
                logic=output.reasoning_trace,
                source_guideline_ids=list(output.source_guideline_ids),
            )
        else:
            for item in output.missing_information:
                if item not in state.risk_assessment.missing_information:
                    state.risk_assessment.missing_information.append(item)
            for guideline_id in output.source_guideline_ids:
                if guideline_id not in state.risk_assessment.source_guideline_ids:
                    state.risk_assessment.source_guideline_ids.append(guideline_id)
        return state.risk_assessment

    def _risk_level_from_behavior_output(self, output: AgentOutput) -> int:
        conclusion = output.conclusion.lower()
        if "high" in conclusion:
            return 8
        if "moderate" in conclusion:
            return 6
        if "play" in conclusion:
            return 2
        return 4

    def _risk_band_from_behavior_output(self, output: AgentOutput) -> RiskBand:
        conclusion = output.conclusion.lower()
        if "high" in conclusion:
            return RiskBand.high
        if "moderate" in conclusion:
            return RiskBand.moderate
        return RiskBand.low

    def _recommended_action_from_behavior_output(self, output: AgentOutput) -> str:
        conclusion = output.conclusion.lower()
        if "high" in conclusion:
            return "separate_and_notify_owner"
        if "resource" in conclusion:
            return "manage_environment_and_monitor"
        if "play" in conclusion:
            return "continue_monitoring"
        return "monitor_and_collect_more_information"

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
