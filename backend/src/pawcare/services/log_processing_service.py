from __future__ import annotations

from dataclasses import dataclass

from pawcare.coordinator import CareCoordinator, CoordinatorResult
from pawcare.schemas.state import (
    BehavioralBaseline,
    DogProfile,
    HealthBaseline,
    RiskBand,
    Species,
    UserResponse,
    UserResponseStatus,
)


@dataclass(frozen=True)
class LogProcessingResult:
    response: UserResponse
    coordinator_result: CoordinatorResult


class LogProcessingService:
    """Product-facing service for processing user care logs.

    This is the layer that turns internal pipeline output into a user-facing
    response. It hides AgentOutput and proposed_update from the user.
    """

    def __init__(self, *, coordinator: CareCoordinator | None = None) -> None:
        self.coordinator = coordinator or CareCoordinator()

    def process_log(
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
    ) -> LogProcessingResult:
        coordinator_result = self.coordinator.handle_log(
            workflow_id=workflow_id,
            dog_id=dog_id,
            raw_text=raw_text,
            timestamp=timestamp,
            dog_profile=dog_profile,
            behavioral_baseline=behavioral_baseline,
            health_baseline=health_baseline,
            species=species,
        )
        response = self._build_user_response(coordinator_result)
        return LogProcessingResult(
            response=response,
            coordinator_result=coordinator_result,
        )

    def _build_user_response(
        self, coordinator_result: CoordinatorResult
    ) -> UserResponse:
        state = coordinator_result.state

        if state.safety_review is not None and state.safety_review.final_status == "blocked_needs_human_review":
            return UserResponse(
                status=UserResponseStatus.needs_review,
                workflow_id=state.workflow_id,
                dog_id=state.dog_id,
                risk_band=state.risk_assessment.risk_band if state.risk_assessment else None,
                message=(
                    "I recorded the update, but the recommendation needs human review before "
                    "it can be shared safely."
                ),
                escalation_conditions=(
                    state.risk_assessment.escalation_conditions if state.risk_assessment else []
                ),
                source_guideline_ids=(
                    state.risk_assessment.source_guideline_ids if state.risk_assessment else []
                ),
            )

        if state.final_recommendation is not None:
            status = self._status_from_risk_band(state.final_recommendation.risk_band)
            return UserResponse(
                status=status,
                workflow_id=state.workflow_id,
                dog_id=state.dog_id,
                risk_band=state.final_recommendation.risk_band,
                message=state.final_recommendation.owner_message
                or state.final_recommendation.summary,
                escalation_conditions=list(state.final_recommendation.escalation_conditions),
                source_guideline_ids=list(state.final_recommendation.source_guideline_ids),
            )

        return UserResponse(
            status=UserResponseStatus.updated,
            workflow_id=state.workflow_id,
            dog_id=state.dog_id,
            risk_band=RiskBand.low,
            message=(
                "Status updated. No clear behavior or safety risk was detected from this entry. "
                "Continue recording appetite, stool, activity, and behavior changes."
            ),
            escalation_conditions=[],
            source_guideline_ids=[],
        )

    def _status_from_risk_band(self, risk_band: RiskBand) -> UserResponseStatus:
        if risk_band in {RiskBand.high, RiskBand.urgent}:
            return UserResponseStatus.escalate
        if risk_band == RiskBand.moderate:
            return UserResponseStatus.attention_needed
        return UserResponseStatus.updated
