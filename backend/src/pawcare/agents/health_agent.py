from __future__ import annotations

from datetime import UTC, datetime

from pawcare.knowledge import get_guideline
from pawcare.schemas.state import (
    ActiveContext,
    AgentOutput,
    Observation,
    ObservationCategory,
    ProposedUpdate,
)


class HealthAgent:
    """Health-domain worker agent backed by approved guideline IDs."""

    agent_name = "HealthAgent"

    def analyze(
        self,
        *,
        active_context: ActiveContext,
        observations: list[Observation],
    ) -> AgentOutput:
        health_observations = [
            observation
            for observation in observations
            if observation.category
            in {
                ObservationCategory.food_intake,
                ObservationCategory.stool,
                ObservationCategory.vomiting,
                ObservationCategory.energy,
                ObservationCategory.mobility,
                ObservationCategory.medication_note,
            }
        ]

        if not health_observations:
            return self._output(
                observations=observations,
                conclusion="no health evidence",
                confidence=0.7,
                missing_information=["health_observation"],
                proposed_update=ProposedUpdate(
                    target_path="current_session_state.pending_conflicts",
                    operation="append",
                    value={
                        "type": "missing_information",
                        "description": "HealthAgent did not receive health observations.",
                    },
                ),
                reasoning_trace="No health-domain observations were provided in active_context.",
                source_guideline_ids=["GL_APPETITE_002"],
            )

        signals = self._signals_from_observations(health_observations)
        guideline_ids = self._guideline_ids_from_signals(signals)
        missing_information = self._missing_information(signals)
        conclusion, proposed_value, confidence = self._conclusion(signals)

        return self._output(
            observations=health_observations,
            conclusion=conclusion,
            confidence=confidence,
            missing_information=missing_information,
            proposed_update=ProposedUpdate(
                target_path="risk_assessment.risk_factors",
                operation="append",
                value=proposed_value,
            ),
            reasoning_trace=self._reasoning_trace(signals=signals, guideline_ids=guideline_ids),
            source_guideline_ids=guideline_ids,
        )

    def _signals_from_observations(self, observations: list[Observation]) -> set[str]:
        signals: set[str] = set()
        for observation in observations:
            context = observation.health_context or {}
            if observation.category == ObservationCategory.food_intake:
                if context.get("food_intake") == "low":
                    signals.add("low_appetite")
            if observation.category == ObservationCategory.stool:
                stool_quality = context.get("stool_quality")
                if stool_quality == "soft":
                    signals.add("soft_stool")
                if stool_quality == "watery":
                    signals.add("watery_diarrhea")
                if stool_quality == "bloody":
                    signals.add("bloody_stool")
                if stool_quality == "black_tarry":
                    signals.add("black_tarry_stool")
            if observation.category == ObservationCategory.vomiting:
                if context.get("vomiting_reported"):
                    signals.add("vomiting")
            if observation.category == ObservationCategory.energy:
                if context.get("energy_level") == "low":
                    signals.add("decreased_activity")
            if observation.category == ObservationCategory.mobility:
                if context.get("mobility") == "limping":
                    signals.add("limping")
                if context.get("weight_bearing") == "non_weight_bearing":
                    signals.add("non_weight_bearing")
                if context.get("post_op_context"):
                    signals.add("acl_surgery")
                if context.get("rehab_exercise"):
                    signals.add("rehab_exercise")
            if observation.category == ObservationCategory.medication_note:
                if context.get("nsaid_or_pain_med_context"):
                    signals.add("medication_use")
        return signals

    def _guideline_ids_from_signals(self, signals: set[str]) -> list[str]:
        guideline_ids: list[str] = []
        if signals & {"soft_stool", "watery_diarrhea", "bloody_stool", "black_tarry_stool"}:
            guideline_ids.append("GL_STOOL_001")
        if "low_appetite" in signals:
            guideline_ids.append("GL_APPETITE_002")
        if "vomiting" in signals:
            guideline_ids.append("GL_VOMITING_001")
        if "decreased_activity" in signals:
            guideline_ids.append("GL_LETHARGY_001")
        if signals & {"limping", "non_weight_bearing"}:
            guideline_ids.append("GL_LAMENESS_001")
        if signals & {"acl_surgery", "non_weight_bearing", "rehab_exercise"}:
            guideline_ids.append("GL_ACL_POSTOP_001")
        if "medication_use" in signals and signals & {
            "vomiting",
            "watery_diarrhea",
            "bloody_stool",
            "black_tarry_stool",
            "low_appetite",
            "decreased_activity",
        }:
            guideline_ids.append("GL_NSAID_SIDE_EFFECT_001")
        return guideline_ids or ["GL_APPETITE_002"]

    def _missing_information(self, signals: set[str]) -> list[str]:
        missing: set[str] = set()
        if "low_appetite" in signals:
            missing.update({"water_intake", "energy_level", "vomiting_status", "stool_status"})
        if signals & {"watery_diarrhea", "bloody_stool", "black_tarry_stool"}:
            missing.update({"stool_frequency", "vomiting_status", "energy_level"})
        if "vomiting" in signals:
            missing.update({"vomiting_frequency", "water_intake", "stool_status"})
        if signals & {"limping", "non_weight_bearing", "acl_surgery", "rehab_exercise"}:
            missing.update({"affected_limb", "pain_signs", "incision_status", "activity_level"})
        return sorted(missing)

    def _conclusion(self, signals: set[str]) -> tuple[str, str, float]:
        if "medication_use" in signals and signals & {"bloody_stool", "black_tarry_stool", "vomiting"}:
            return "high medication safety concern", "possible medication side-effect warning signs", 0.88
        if signals & {"bloody_stool", "black_tarry_stool"}:
            return "high digestive risk profile", "blood or black/tarry stool reported", 0.86
        if "acl_surgery" in signals and "non_weight_bearing" in signals:
            return "high post-op mobility concern", "post-op non-weight-bearing or severe mobility change", 0.86
        if "rehab_exercise" in signals and "acl_surgery" in signals:
            return "moderate post-op rehab concern", "post-op rehabilitation difficulty or exercise reluctance", 0.8
        if "vomiting" in signals and ("watery_diarrhea" in signals or "decreased_activity" in signals):
            return "high combined health risk profile", "vomiting combined with diarrhea or decreased activity", 0.84
        if "low_appetite" in signals:
            return "moderate appetite concern", "appetite below baseline or expected intake", 0.78
        if signals & {"limping", "non_weight_bearing"}:
            return "moderate mobility concern", "limping or weight-bearing change", 0.78
        if "soft_stool" in signals:
            return "low stool monitoring concern", "soft stool reported", 0.72
        return "low health monitoring concern", "health observation recorded", 0.65

    def _reasoning_trace(self, *, signals: set[str], guideline_ids: list[str]) -> str:
        topics = [get_guideline(guideline_id).topic for guideline_id in guideline_ids]
        return (
            "Observed health signals: "
            + ", ".join(sorted(signals))
            + ". Applied guidelines: "
            + "; ".join(topics)
            + "."
        )

    def _output(
        self,
        *,
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
            input_observation_ids=[observation.observation_id for observation in observations],
            conclusion=conclusion,
            confidence=confidence,
            missing_information=missing_information,
            proposed_update=proposed_update,
            reasoning_trace=reasoning_trace,
            source_guideline_ids=source_guideline_ids,
        )
