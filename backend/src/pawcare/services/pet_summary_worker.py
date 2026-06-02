from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from pawcare.schemas.state import Observation
from pawcare.services.pet_models import (
    DailyPetSummary,
    MonthlyPetSummary,
    PetRecord,
    WeeklyPetSummary,
)


class SummaryWorker:
    """Build compact pet memory summaries from structured observations."""

    def build_daily_summaries(self, *, pet: PetRecord) -> list[DailyPetSummary]:
        grouped: dict[str, list[Observation]] = defaultdict(list)
        for observation in pet.observations:
            grouped[self._date_key(observation.timestamp)].append(observation)
        return [
            DailyPetSummary(
                user_id=pet.user_id,
                pet_id=pet.pet_id,
                date=day,
                summary=self._summary_text(observations),
                domains=self._domains(observations),
                active_issues=self._active_issues(observations),
                important_flags=self._important_flags(observations),
                observation_count=len(observations),
            )
            for day, observations in sorted(grouped.items())
        ]

    def build_weekly_summaries(self, *, pet: PetRecord) -> list[WeeklyPetSummary]:
        grouped: dict[str, list[Observation]] = defaultdict(list)
        for observation in pet.observations:
            grouped[self._week_start(self._date_key(observation.timestamp))].append(observation)
        return [
            WeeklyPetSummary(
                user_id=pet.user_id,
                pet_id=pet.pet_id,
                week_start=week_start,
                summary=self._summary_text(observations),
                domains=self._domains(observations),
                active_issues=self._active_issues(observations),
                important_flags=self._important_flags(observations),
                observation_count=len(observations),
            )
            for week_start, observations in sorted(grouped.items())
        ]

    def build_monthly_summaries(self, *, pet: PetRecord) -> list[MonthlyPetSummary]:
        grouped: dict[str, list[Observation]] = defaultdict(list)
        for observation in pet.observations:
            grouped[self._date_key(observation.timestamp)[:7]].append(observation)
        return [
            MonthlyPetSummary(
                user_id=pet.user_id,
                pet_id=pet.pet_id,
                month=month,
                summary=self._summary_text(observations),
                domains=self._domains(observations),
                active_issues=self._active_issues(observations),
                important_flags=self._important_flags(observations),
                observation_count=len(observations),
            )
            for month, observations in sorted(grouped.items())
        ]

    def rebuild_for_pet(self, *, repository, user_id: str, pet_id: str) -> None:
        pet = repository.get_pet(user_id=user_id, pet_id=pet_id)
        repository.save_daily_summaries(
            user_id=user_id,
            pet_id=pet_id,
            summaries=self.build_daily_summaries(pet=pet),
        )
        repository.save_weekly_summaries(
            user_id=user_id,
            pet_id=pet_id,
            summaries=self.build_weekly_summaries(pet=pet),
        )
        repository.save_monthly_summaries(
            user_id=user_id,
            pet_id=pet_id,
            summaries=self.build_monthly_summaries(pet=pet),
        )

    def _summary_text(self, observations: list[Observation]) -> str:
        categories = ", ".join(sorted({str(observation.category) for observation in observations}))
        issue_text = ", ".join(self._active_issues(observations))
        if issue_text:
            return f"{len(observations)} observations across {categories}; active issues: {issue_text}."
        return f"{len(observations)} observations across {categories}; no high-signal issue summarized."

    def _domains(self, observations: list[Observation]) -> list[str]:
        domains: set[str] = set()
        for observation in observations:
            category = str(observation.category)
            if category == "social_interaction":
                domains.add("behavior")
            elif category == "other":
                domains.add("general")
            else:
                domains.add("health")
            condition_domain = (observation.health_context or {}).get("condition_domain")
            if condition_domain:
                domains.add(str(condition_domain))
        return sorted(domains)

    def _active_issues(self, observations: list[Observation]) -> list[str]:
        issues: set[str] = set()
        for observation in observations:
            context = observation.health_context or {}
            category = str(observation.category)
            if category == "food_intake" and context.get("food_intake") == "low":
                issues.add("low appetite")
            if category == "stool" and context.get("stool_quality") in {"bloody", "black_tarry", "watery"}:
                issues.add(f"{context.get('stool_quality')} stool")
            if category == "urination" or context.get("urinary_obstruction"):
                issues.add("urinary concern")
            if category == "mobility" and context.get("weight_bearing") == "non_weight_bearing":
                issues.add("non-weight-bearing mobility change")
            if context.get("respiratory_distress"):
                issues.add("respiratory concern")
            if str(observation.category) == "social_interaction":
                issues.add("behavior/social signal")
        return sorted(issues)

    def _important_flags(self, observations: list[Observation]) -> list[str]:
        flags: set[str] = set()
        for observation in observations:
            context = observation.health_context or {}
            raw = observation.raw_text.lower()
            if any(term in raw for term in ["blood", "bloody", "black/tarry", "cannot pee", "couldn't pee", "seizure", "bloat"]):
                flags.add(observation.raw_text)
            if context.get("urgent_red_flag") or context.get("urinary_obstruction") or context.get("respiratory_distress"):
                flags.add(observation.raw_text)
        return sorted(flags)

    def _date_key(self, timestamp: str | None) -> str:
        if not timestamp:
            return date.today().isoformat()
        normalized = timestamp[:-1] + "+00:00" if timestamp.endswith("Z") else timestamp
        try:
            return datetime.fromisoformat(normalized).date().isoformat()
        except ValueError:
            return str(timestamp)[:10]

    def _week_start(self, value: str) -> str:
        try:
            day = date.fromisoformat(value)
        except ValueError:
            return value
        return (day - timedelta(days=day.weekday())).isoformat()
