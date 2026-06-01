from __future__ import annotations

from datetime import UTC, datetime

from pawcare.schemas.state import (
    ActiveContext,
    AgentOutput,
    BodyLanguageSignal,
    InteractionType,
    Observation,
    ObservationCategory,
    ProposedUpdate,
    ResourceType,
    VocalizationSignal,
)


class BehaviorAgent:
    """Behavior-domain worker agent.

    This agent reads only the active context and the observation copies provided
    by the Coordinator. It returns proposed updates and never mutates global
    state directly.
    """

    agent_name = "BehaviorAgent"

    def analyze(
        self,
        *,
        active_context: ActiveContext,
        observations: list[Observation],
    ) -> AgentOutput:
        social_observations = [
            observation
            for observation in observations
            if observation.category == ObservationCategory.social_interaction
        ]

        if not social_observations:
            return self._output(
                active_context=active_context,
                observations=observations,
                conclusion="no social interaction evidence",
                confidence=0.7,
                missing_information=["social_context"],
                proposed_update=ProposedUpdate(
                    target_path="current_session_state.pending_conflicts",
                    operation="append",
                    value={
                        "type": "missing_information",
                        "description": "BehaviorAgent did not receive social interaction observations.",
                    },
                ),
                reasoning_trace="No social_interaction observations were provided in active_context.",
                source_guideline_ids=["GL_SOCIAL_STRESS_001"],
            )

        strongest = max(
            social_observations,
            key=lambda observation: observation.severity_score or 0,
        )
        social_context = strongest.social_context
        if social_context is None:
            return self._output(
                active_context=active_context,
                observations=[strongest],
                conclusion="missing social context",
                confidence=0.75,
                missing_information=["social_context"],
                proposed_update=ProposedUpdate(
                    target_path="current_session_state.pending_conflicts",
                    operation="append",
                    value={
                        "type": "missing_information",
                        "description": "social_interaction observation did not include social_context.",
                    },
                ),
                reasoning_trace="The observation was marked social_interaction but lacked social_context.",
                source_guideline_ids=["GL_SOCIAL_STRESS_001"],
            )

        body_language = set(social_context.signals.body_language)
        vocalization = set(social_context.signals.vocalization)
        resource = social_context.resource_involved
        is_resource_context = bool(resource.present and resource.type != ResourceType.none)
        stress_signals = body_language & {
            BodyLanguageSignal.lip_licking.value,
            BodyLanguageSignal.yawning.value,
            BodyLanguageSignal.whale_eye.value,
            BodyLanguageSignal.frozen.value,
            BodyLanguageSignal.stiff_body.value,
            BodyLanguageSignal.avoidance.value,
            BodyLanguageSignal.turning_away.value,
            BodyLanguageSignal.lowered_tail.value,
            BodyLanguageSignal.tail_tucked.value,
            BodyLanguageSignal.ears_back.value,
            BodyLanguageSignal.crouching.value,
            BodyLanguageSignal.puffed_tail.value,
            BodyLanguageSignal.arched_back.value,
            BodyLanguageSignal.flattened_ears.value,
            BodyLanguageSignal.hiding.value,
        }
        escalation_signals = body_language & {
            BodyLanguageSignal.air_snap.value,
            BodyLanguageSignal.muzzle_punch.value,
        }
        escalation_vocals = vocalization & {
            VocalizationSignal.growl.value,
            VocalizationSignal.snarl.value,
            VocalizationSignal.yelp.value,
            VocalizationSignal.hissing.value if hasattr(VocalizationSignal, "hissing") else "",
        }
        play_signals = {
            BodyLanguageSignal.play_bow.value,
            BodyLanguageSignal.loose_body.value,
        }

        if escalation_signals or escalation_vocals:
            return self._output(
                active_context=active_context,
                observations=[strongest],
                conclusion="high social safety concern",
                confidence=0.88,
                missing_information=self._missing_resource_history(active_context),
                proposed_update=ProposedUpdate(
                    target_path="risk_assessment.risk_factors",
                    operation="append",
                    value="escalation signals during social interaction",
                ),
                reasoning_trace=self._with_behavior_context(
                    active_context,
                    "Growling, snapping, yelping, or similar escalation signals require "
                    "conservative management and Coordinator review."
                ),
                source_guideline_ids=self._guideline_ids(is_resource_context=is_resource_context),
            )

        if stress_signals and is_resource_context:
            return self._output(
                active_context=active_context,
                observations=[strongest],
                conclusion="moderate social stress near resource",
                confidence=0.84,
                missing_information=self._missing_resource_history(active_context),
                proposed_update=ProposedUpdate(
                    target_path="risk_assessment.risk_factors",
                    operation="append",
                    value="stress signals near high-value resource",
                ),
                reasoning_trace=self._with_behavior_context(
                    active_context,
                    "Stress body-language signals appeared in a resource context. "
                    "This should be treated as a social/resource risk factor, not ignored."
                ),
                source_guideline_ids=self._guideline_ids(is_resource_context=True),
            )

        if stress_signals:
            return self._output(
                active_context=active_context,
                observations=[strongest],
                conclusion="low to moderate social stress",
                confidence=0.78,
                missing_information=[],
                proposed_update=ProposedUpdate(
                    target_path="risk_assessment.risk_factors",
                    operation="append",
                    value="subtle social stress signals",
                ),
                reasoning_trace=self._with_behavior_context(
                    active_context,
                    "Subtle stress body-language signals were present even without overt aggression."
                ),
                source_guideline_ids=["GL_SOCIAL_STRESS_001"],
            )

        if play_signals.issubset(body_language) or social_context.interaction_type == InteractionType.play:
            return self._output(
                active_context=active_context,
                observations=[strongest],
                conclusion="likely appropriate play",
                confidence=0.76,
                missing_information=[],
                proposed_update=ProposedUpdate(
                    target_path="risk_assessment.protective_factors",
                    operation="append",
                    value="loose body and play bow suggest appropriate play context",
                ),
                reasoning_trace=self._with_behavior_context(
                    active_context,
                    "Loose body language and play bow are more consistent with appropriate play "
                    "when no stress or injury signals are present."
                ),
                source_guideline_ids=["GL_SOCIAL_PLAY_001"],
            )

        return self._output(
            active_context=active_context,
            observations=[strongest],
            conclusion="insufficient behavior signal",
            confidence=0.55,
            missing_information=["additional body language", "interaction duration"],
            proposed_update=ProposedUpdate(
                target_path="current_session_state.pending_conflicts",
                operation="append",
                value={
                    "type": "missing_information",
                    "description": "BehaviorAgent needs more social signal detail before risk interpretation.",
                },
            ),
            reasoning_trace="The social observation did not include enough behavior signal detail.",
            source_guideline_ids=["GL_SOCIAL_STRESS_001"],
        )

    def _output(
        self,
        *,
        active_context: ActiveContext,
        observations: list[Observation],
        conclusion: str,
        confidence: float,
        missing_information: list[str],
        proposed_update: ProposedUpdate,
        reasoning_trace: str,
        source_guideline_ids: list[str],
    ) -> AgentOutput:
        return AgentOutput(
            agent=self.agent_name,
            timestamp=datetime.now(UTC).isoformat(),
            input_active_context_id=None,
            input_observation_ids=[
                observation.observation_id for observation in observations
            ],
            conclusion=conclusion,
            confidence=confidence,
            missing_information=missing_information,
            proposed_update=proposed_update,
            reasoning_trace=reasoning_trace,
            source_guideline_ids=source_guideline_ids,
        )

    def _guideline_ids(self, *, is_resource_context: bool) -> list[str]:
        guideline_ids = ["GL_SOCIAL_STRESS_001"]
        if is_resource_context:
            guideline_ids.append("GL_RESOURCE_GUARDING_001")
        return guideline_ids

    def _missing_resource_history(self, active_context: ActiveContext) -> list[str]:
        guarding_profile = active_context.relevant_baseline.get(
            "resource_guarding_profile"
        )
        if guarding_profile:
            return []
        return ["resource_guarding_history"]

    def _with_behavior_context(self, active_context: ActiveContext, trace: str) -> str:
        references = active_context.relevant_baseline.get("behavior_references", [])
        names: list[str] = []
        if isinstance(references, list):
            for reference in references:
                if isinstance(reference, dict) and reference.get("source_name"):
                    names.append(str(reference["source_name"]))
        if not names:
            return trace
        return trace + " Behavior context: " + "; ".join(names[:3]) + "."
